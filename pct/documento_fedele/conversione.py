"""La conversione di un PDF in HTML fedele: mette insieme le parti.

Legge le righe, ne fa paragrafi, riconosce tabelle e immagini, toglie testate
e piedi ripetuti, dichiara formato e margini."""

from __future__ import annotations

import io
import logging
import re
import statistics
from typing import Iterable, Optional

from .geometria import Riquadro
from .immagini import estrai_grafica, estrai_immagini
from .caratteri_incorporati import (
    blocco_stile,
    caratteri_della_pagina,
    da_incorporare,
)
from .lettura import leggi_righe
from .modello import DocumentoConvertito, PaginaConvertita, Riga, Tratto
from .pagina import _formato, _margini, _pagina_esatta, _testate_e_piedi
from .paragrafi import _html_tratti, costruisci_paragrafi
from .sorgente import DocumentoSorgente, PaginaSorgente
from .tabelle import estrai_tabelle
from .taratura import Taratura, _pt, pila_font

_LOG = logging.getLogger(__name__)

# ===========================================================================
# 7. Conversione
# ===========================================================================

def _ocr_pagina(documento: DocumentoSorgente, indice: int, lingua: str) -> tuple[Optional[list[Riga]], str]:
    """Pagina scansionata: la legge il motore OCR unico, non una copia locale.

    In IUSENTRA il riconoscimento ottico ha un solo motore, `legal_ocr/motore/`
    (vedi docs/OCR_LEGAL.md): chiamare `pytesseract` da qui creerebbe un
    secondo lettore con tarature proprie, e due lettori che leggono lo stesso
    atto in due modi diversi sono peggio di uno solo.

    Del riconoscimento qui serve la **posizione** oltre al testo: le parole
    tornano con il loro riquadro, e da quelle si ricostruiscono le righe. Se il
    motore non e' disponibile la pagina resta com'e': una scansione senza testo
    e' un difetto dichiarato, non un errore da propagare. Restituisce le righe
    e **il motivo** quando non ce ne sono: un guasto si legge, non si indovina
    — la prima stesura inghiottiva ogni eccezione e un semplice import
    mancante spegneva il riconoscimento su tutte le scansioni, senza dirlo.
    """
    try:
        from PIL import Image

        from legal_ocr.motore import runtime as motore_runtime
        from legal_ocr.motore.lettura import leggi_immagine
    except ImportError as errore:  # pragma: no cover - ambienti senza OCR
        return None, f"motore di riconoscimento non installato ({errore})"
    try:
        import pytesseract as _motore  # il modulo, che il motore unico usa al posto nostro

        motore_runtime.configura(_motore)
    except Exception as errore:  # pragma: no cover - Tesseract non installato
        return None, f"Tesseract non configurato ({errore})"

    try:
        pagina = documento[indice]
        with Image.open(io.BytesIO(pagina.png(dpi=DPI_OCR))) as immagine:
            lettura = leggi_immagine(immagine.convert("L"), pytesseract=_motore,
                                     lingua=lingua or "ita", con_pdf=False)
    except Exception as errore:
        _LOG.debug("riconoscimento ottico non riuscito a pagina %s", indice + 1, exc_info=True)
        return None, f"{type(errore).__name__}: {errore}"

    scala = 72.0 / DPI_OCR
    corpo_stimato = _corpo_da_parole(lettura.parole, scala)
    per_riga: dict[tuple[int, int, int], list[dict]] = {}
    for parola in lettura.parole:
        if not str(parola.get("text") or "").strip():
            continue
        chiave = (int(parola.get("block") or 0), int(parola.get("par") or 0), int(parola.get("line") or 0))
        per_riga.setdefault(chiave, []).append(parola)

    fuori: list[Riga] = []
    for chiave in sorted(per_riga, key=lambda k: (min(int(p["top"]) for p in per_riga[k]), k)):
        parole = sorted(per_riga[chiave], key=lambda p: int(p["left"]))
        tratti = [
            Tratto(testo=str(parola["text"]) + " ", famiglia=pila_font("Times New Roman"),
                   corpo=max(6.0, round(int(parola["height"]) * scala * ALTEZZA_IN_CORPO, 1)) or corpo_stimato)
            for parola in parole
        ]
        if not tratti:
            continue
        x0 = min(int(p["left"]) for p in parole) * scala
        x1 = max(int(p["left"]) + int(p["width"]) for p in parole) * scala
        y0 = min(int(p["top"]) for p in parole) * scala
        y1 = max(int(p["top"]) + int(p["height"]) for p in parole) * scala
        fuori.append(Riga(tratti=tratti, bbox=(x0, y0, x1, y1), origine_y=y1))
    return (fuori, "") if fuori else (None, "nessuna parola riconosciuta nella pagina")


def _corpo_da_parole(parole: list[dict], scala: float) -> float:
    """Il corpo mediano della pagina: una riga isolata non detta il corpo di tutte."""
    altezze = [int(p.get("height") or 0) * scala for p in parole if int(p.get("height") or 0) > 0]
    if not altezze:
        return 11.0
    return max(6.0, round(statistics.median(altezze) * ALTEZZA_IN_CORPO, 1))


_RE_ALIAS = re.compile(r"^iu-[0-9a-f]+$")


def _alias_incorporato(pila: str) -> str:
    """L'alias del carattere incorporato, se questa pila ne ha uno in testa."""
    prima = str(pila or "").split(",")[0].strip().strip("'\"")
    return prima if _RE_ALIAS.match(prima) else ""


def _e_scansione(testo_letto: int, tracciati: int) -> bool:
    """Se questa pagina e' una fotografia, e quindi va letta col riconoscimento.

    Poche parole non bastano a dirlo. Un modulo del tribunale — una nota di
    iscrizione a ruolo, un invito al pagamento — di parole ne ha poche e ha la
    griglia disegnata: mandandolo al riconoscimento ottico si perde la griglia
    insieme alle caselle, e quello che torna e' un elenco di frasi sciolte.

    Una scansione, invece, e' una fotografia: dentro ha un disegno solo,
    l'immagine, e di righe e rettangoli non ne ha. Quindi: poco testo **e**
    nessun tracciato.
    """
    if testo_letto >= Taratura.SOGLIA_SCANSIONE:
        return False
    if testo_letto and tracciati >= Taratura.VETTORI_NON_SCANSIONE:
        return False
    return True


def _senza_alias(pila: str) -> str:
    """La pila delle famiglie senza il carattere incorporato in testa."""
    voci = [v.strip() for v in str(pila or "").split(",")]
    if voci and _RE_ALIAS.match(voci[0].strip("'\"")):
        voci = voci[1:]
    return ", ".join(voci) if voci else pila


def _famiglia_da_pila(pila: str) -> str:
    """La famiglia dell'editor dentro una pila CSS come `'Times', 'Times New Roman', serif`.

    L'ultima voce e' il generico (serif, sans-serif, monospace); quella prima
    e' la famiglia che l'editor offre in tendina.
    """
    voci = [voce.strip().strip("'\"") for voce in str(pila or "").split(",")]
    voci = [voce for voce in voci if voce and voce not in ("serif", "sans-serif", "monospace")]
    return voci[-1] if voci else ""


#: risoluzione con cui si rasterizza una pagina scansionata prima di leggerla
DPI_OCR = 300
#: dall'altezza del riquadro di una parola al corpo del carattere: il riquadro
#: comprende ascendenti e discendenti, il corpo e' poco meno
ALTEZZA_IN_CORPO = 0.78

#: sotto questo numero di righe la colonna di testo non si deduce dal contenuto
RIGHE_PER_DEDURRE_LA_COLONNA = 3


def _allineamento_pagina(righe: list[Riga], margini, larghezza: float) -> str:
    """Come e' allineato il corpo della pagina.

    Quello che distingue il giustificato non e' quante righe toccano il margine
    destro — l'ultima riga di ogni capoverso non lo tocca — ma che quelle che
    lo toccano finiscano tutte nello stesso punto.
    """
    if len(righe) < 4:
        return "left"
    conteggio: dict[int, int] = {}
    for r in righe:
        chiave = int(round(r.bbox[2]))
        conteggio[chiave] = conteggio.get(chiave, 0) + 1
    ricorrente, quante = max(conteggio.items(), key=lambda voce: voce[1])
    if quante > len(righe) * 0.30:
        return "justify"
    return "left"


def _interlinea(righe: list[Riga], corpo: float) -> float:
    """La distanza fra le basi di due righe consecutive, in punti.

    Si prende la mediana dei salti, non la media: in un atto ci sono sempre
    righe piu' distanti — dopo un titolo, prima di un elenco — e la media le
    farebbe pesare come se fossero la regola.
    """
    if len(righe) < 3:
        return round(corpo * 1.2, 1)
    ordinate = sorted(righe, key=lambda r: r.origine_y)
    salti = [
        ordinate[i + 1].origine_y - ordinate[i].origine_y
        for i in range(len(ordinate) - 1)
    ]
    salti = sorted(s for s in salti if corpo * 0.6 < s < corpo * 4)
    if not salti:
        return round(corpo * 1.2, 1)
    return round(salti[len(salti) // 2], 1)


def _colonna(pagina: PaginaSorgente, righe: list[Riga],
             margini: tuple[float, float, float, float]) -> tuple[float, float]:
    """I bordi sinistro e destro della colonna di testo, per giudicare gli allineamenti.

    Di norma la colonna si deduce dal contenuto: dove comincia la riga piu' a
    sinistra e dove finisce quella piu' a destra. Su una pagina con poche righe
    quella deduzione si morde la coda — una sola riga definisce una colonna
    larga quanto se stessa, quindi tocca entrambi i bordi e risulta
    giustificata. Ma un titolo solo sulla pagina, come la copertina di una
    procura alle liti, e' centrato rispetto al **foglio**: con poche righe si
    assume percio' il foglio intero come colonna, e la centratura si vede.
    """
    if len({round(r.bbox[1], 1) for r in righe}) >= RIGHE_PER_DEDURRE_LA_COLONNA:
        return margini[3], pagina.rect.width - margini[1]
    return 0.0, pagina.rect.width


def converti(
    percorso: str,
    *,
    modo: str = "fedele",
    lingua_ocr: str = "ita",
    ocr_se_scansione: bool = True,
    pagine: Optional[Iterable[int]] = None,
    max_pagine: int = 400,
    max_pagine_ocr: int = 80,
    avanzamento=None,
) -> DocumentoConvertito:
    """
    `avanzamento` viene richiamato come avanzamento(fatte, totali) a ogni
    pagina: serve alla barra di caricamento dell'editor sui documenti lunghi.
    `max_pagine_ocr` evita che una scansione di centinaia di pagine tenga
    occupato un lavoratore per mezz'ora.
    """
    documento = DocumentoSorgente(percorso)
    try:
        esito = DocumentoConvertito()
        famiglie: set[str] = set()
        selezione = set(pagine) if pagine is not None else None
        tutte_righe: list[list[Riga]] = []
        grezzo: list[dict] = []
        pagine_ocr = 0
        totali = min(len(documento), max_pagine)

        for indice, pagina in enumerate(documento):
            if indice >= max_pagine:
                esito.avvisi.append(
                    f"documento troncato a {max_pagine} pagine"
                )
                break
            if selezione is not None and (indice + 1) not in selezione:
                continue

            # I caratteri che il PDF si porta dentro: servono per i
            # calligrafici e per tutto quello che un equivalente aperto non ce
            # l'ha. Si leggono prima delle righe perche' il loro alias entra
            # nella pila delle famiglie di ogni tratto.
            try:
                tutti = caratteri_della_pagina(pagina)
                # l'alias si mette solo ai caratteri che ci porteremo dietro:
                # per Times New Roman o Calibri c'e' l'equivalente aperto, che
                # e' un carattere intero e regge anche il testo riscritto
                incorporati_pagina = da_incorporare(
                    tutti, {v["alias"] for v in tutti.values()}
                )
            except Exception:
                incorporati_pagina = {}
            righe = leggi_righe(pagina, incorporati_pagina)
            for riga in righe:
                for tratto in riga.tratti:
                    famiglie.add(_famiglia_da_pila(tratto.famiglia))
            da_ocr = False
            try:
                tracciati = len(pagina.rettangoli) + len(pagina.linee)
            except Exception:
                tracciati = 0
            scansione = _e_scansione(
                sum(len(r.testo) for r in righe), tracciati
            )
            if scansione and ocr_se_scansione and pagine_ocr >= max_pagine_ocr:
                esito.avvisi.append(
                    f"pagina {indice + 1}: riconoscimento ottico non eseguito "
                    f"(oltre le {max_pagine_ocr} pagine consentite)"
                )
            elif ocr_se_scansione and scansione:
                riconosciute, motivo = _ocr_pagina(documento, indice, lingua_ocr)
                pagine_ocr += 1
                if riconosciute:
                    righe, da_ocr = riconosciute, True
                else:
                    esito.avvisi.append(
                        f"pagina {indice + 1}: scansione senza testo, "
                        f"riconoscimento ottico non riuscito — {motivo}"
                    )

            if righe:
                testo_sx = min(r.bbox[0] for r in righe)
                testo_dx = max(r.bbox[2] for r in righe)
            else:
                testo_sx, testo_dx = 0.0, pagina.rect.width
            tabelle = ([] if da_ocr
                       else estrai_tabelle(pagina, righe, testo_sx, testo_dx))
            immagini = estrai_immagini(pagina, pagina.rect.width,
                                        salta_pagina_intera=da_ocr)
            occupati = [Riquadro(t.bbox) for t in tabelle] + [Riquadro(i.bbox) for i in immagini]
            grafica = [] if da_ocr else estrai_grafica(pagina, occupati, righe=righe)

            grezzo.append({
                "pagina": pagina, "indice": indice, "righe": righe,
                "tabelle": tabelle, "immagini": immagini, "grafica": grafica,
                "da_ocr": da_ocr,
            })
            tutte_righe.append(righe)
            if avanzamento:
                try:
                    avanzamento(len(grezzo), totali)
                except Exception:
                    pass

        altezza = documento[0].rect.height if len(documento) else 842.0
        testate, piedi = _testate_e_piedi(tutte_righe, altezza)

        for voce in grezzo:
            pagina: PaginaSorgente = voce["pagina"]
            righe: list[Riga] = voce["righe"]
            tabelle, immagini, grafica = voce["tabelle"], voce["immagini"], voce["grafica"]

            occupati = [Riquadro(t.bbox) for t in tabelle]
            libere = [
                r for r in righe
                if not any(t.intersects(Riquadro(r.bbox))
                           and (t & Riquadro(r.bbox)).get_area()
                           > Riquadro(r.bbox).get_area() * 0.5
                           for t in occupati)
            ]
            corpo_pagina = (statistics.median([r.corpo for r in libere])
                            if libere else 11.0)
            # la famiglia della pagina non porta l'alias: quello e' del
            # singolo tratto, e in testa alla pila della pagina spegnerebbe il
            # riconoscimento dell'equivalente metrico per tutto il documento
            famiglia_pagina = _senza_alias(statistics.mode(
                [t.famiglia for r in libere for t in r.tratti if t.testo.strip()]
            )) if libere else pila_font("Times New Roman")

            nome_formato, orientamento = _formato(pagina)
            # I margini sono quelli del testo. Immagini e grafica non entrano
            # piu' nel flusso — si disegnano al loro riquadro — e contarle qui
            # faceva cominciare la pagina dove comincia il timbro invece che
            # dove comincia l'atto: sette millimetri piu' su, tutte le righe.
            margini = _margini(pagina, righe, tabelle)

            if modo == "esatto":
                html = _pagina_esatta(pagina, righe, immagini, grafica, voce["indice"] + 1)
            else:
                testa = [r for r in libere
                         if re.sub(r"\d+", "#", r.testo.strip()) in testate]
                piede = [r for r in libere
                         if re.sub(r"\d+", "#", r.testo.strip()) in piedi]
                centro = [r for r in libere if r not in testa and r not in piede]

                sinistra, destra = _colonna(pagina, centro, margini)
                elementi = (
                    costruisci_paragrafi(centro, sinistra, destra,
                                         corpo_pagina, famiglia_pagina)
                    + tabelle + immagini + grafica
                )
                elementi.sort(key=lambda e: e.top)
                corpo_html = "".join(e.html for e in elementi)

                # Testata e piede passano dalla stessa costruzione del
                # corpo: rendendoli a mano, centrati e senza misure, la carta
                # intestata veniva fuori alta il doppio e spingeva giu' tutta
                # la pagina — trentotto punti su una citazione di sedici
                # pagine, cioe' nessuna riga al suo posto.
                if testa:
                    intestazione = "".join(
                        e.html for e in costruisci_paragrafi(
                            testa, sinistra, destra, corpo_pagina, famiglia_pagina,
                            seguito=centro[0] if centro else None,
                        )
                    )
                    corpo_html = (f'<header class="iu-doc-testata">{intestazione}</header>'
                                  + corpo_html)
                if piede:
                    fondo = "".join(
                        e.html for e in costruisci_paragrafi(
                            piede, sinistra, destra, corpo_pagina, famiglia_pagina,
                        )
                    )
                    # il piede porta scritta la sua altezza: non sta nel
                    # flusso del testo — sotto l'ultima riga reportlab tiene
                    # fermo un passo di interlinea, e il numero di pagina non
                    # ci starebbe piu' dentro il foglio — si disegna dov'era
                    corpo_html += (
                        f'<footer class="iu-doc-piede"'
                        f' data-alto="{_pt(piede[0].bbox[1])}">{fondo}</footer>'
                    )

                # La pagina porta con se' le sue misure. Servono a chi la
                # riesporta in PDF: senza, l'esportazione rifa' il documento
                # con margini e interlinea suoi, e un atto di sedici pagine ne
                # esce venti.
                # I caratteri incorporati viaggiano con la pagina: chi la
                # riscrive non ha il PDF di partenza, ha solo questo HTML. Si
                # portano solo quelli usati davvero e senza equivalente
                # aperto — in pratica i calligrafici — perche' un carattere
                # intero pesa duecento kilobyte e non serve.
                usati = {
                    _alias_incorporato(t.famiglia)
                    for r in righe for t in r.tratti if t.testo.strip()
                }
                stile_caratteri = blocco_stile({
                    nome: voce for nome, voce in incorporati_pagina.items()
                    if voce["alias"] in usati
                })
                corpo_html = stile_caratteri + corpo_html

                html = (
                    f'<section class="iu-doc-pagina" data-pagina="{voce["indice"] + 1}"'
                    f' data-origine="{"ocr" if voce["da_ocr"] else "testo"}"'
                    f' data-larghezza="{_pt(pagina.rect.width)}"'
                    f' data-altezza="{_pt(pagina.rect.height)}"'
                    f' data-margine-alto="{_pt(margini[0])}"'
                    f' data-margine-destro="{_pt(margini[1])}"'
                    f' data-margine-basso="{_pt(margini[2])}"'
                    f' data-margine-sinistro="{_pt(margini[3])}"'
                    f' data-interlinea="{_pt(_interlinea(libere, corpo_pagina))}"'
                    f' data-allineamento="{_allineamento_pagina(libere, margini, pagina.rect.width)}"'
                    f' style="font-family:{famiglia_pagina};'
                    f'font-size:{_pt(corpo_pagina)}pt">{corpo_html}</section>'
                )

            esito.pagine.append(PaginaConvertita(
                numero=voce["indice"] + 1,
                larghezza=pagina.rect.width,
                altezza=pagina.rect.height,
                orientamento=orientamento,
                margini=margini,
                html=html,
                da_ocr=voce["da_ocr"],
                elementi=len(righe),
                tabelle=len(tabelle),
                immagini=len(immagini) + len(grafica),
            ))

        if esito.pagine:
            prima = esito.pagine[0]
            nome_formato, orientamento = _formato(documento[0])
            esito.formato = {
                "formato": nome_formato,
                "orientamento": orientamento,
                "larghezza_pt": round(prima.larghezza, 1),
                "altezza_pt": round(prima.altezza, 1),
                "margini_pt": {
                    "alto": round(prima.margini[0], 1),
                    "destro": round(prima.margini[1], 1),
                    "basso": round(prima.margini[2], 1),
                    "sinistro": round(prima.margini[3], 1),
                },
            }
        esito.html = "".join(p.html for p in esito.pagine)
        esito.caratteri = sorted(f for f in famiglie if f)
        return esito
    finally:
        documento.close()
