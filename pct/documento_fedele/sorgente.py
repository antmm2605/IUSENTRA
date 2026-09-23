"""La pagina del PDF da leggere, senza PyMuPDF.

`documento_fedele` chiedeva tutto a una `fitz.Page`: gli span di testo con i
loro attributi, i collegamenti, le linee disegnate, i rettangoli pieni, e il
rendering di un ritaglio per le immagini. Qui quella pagina diventa
`PaginaSorgente`, che mette insieme due librerie permissive: pdfplumber (MIT)
per il testo e la geometria, PDFium (BSD, via pypdfium2) per il rendering.

La struttura degli span riproduce quella che PyMuPDF restituiva con
`get_text("rawdict")` — stesse chiavi, stesso significato — perche' il codice
che la consuma (`_tratti_da_span`) resta com'era: e' la parte che decide
sottolineature, evidenziature e collegamenti carattere per carattere, ed e'
stata tarata su documenti veri. Cambiare insieme lettore e logica avrebbe
reso impossibile capire chi ha rotto cosa.
"""

from __future__ import annotations

import io
import statistics
import struct
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium

from .geometria import Riquadro

#: I bit dei flag di span, come li scriveva PyMuPDF. Il codice che li legge
#: non e' cambiato, quindi i valori devono restare questi.
APICE, CORSIVO, GRAZIE, MONO, GRASSETTO = 1, 2, 4, 8, 16

#: Un elemento disegnato piu' basso di cosi', e piu' largo di `FILETTO_LARGHEZZA_MINIMA`,
#: e' un filetto: una sottolineatura, una barratura o il bordo di una tabella.
FILETTO_ALTEZZA_MASSIMA = 2.4
FILETTO_LARGHEZZA_MINIMA = 5.0

#: Un rettangolo pieno di queste misure, dietro il testo, e' un'evidenziatura.
EVIDENZIATURA_ALTEZZA_MINIMA = 4.0
EVIDENZIATURA_ALTEZZA_MASSIMA = 26.0
EVIDENZIATURA_LARGHEZZA_MINIMA = 8.0

#: Il bianco non evidenzia niente: e' lo sfondo della pagina.
BIANCHI = {"#ffffff", "#fefefe"}

#: Nei PDF lo spazio quasi mai e' un carattere: e' un salto di posizione.
#: Oltre questo stacco, misurato in frazione del corpo, fra la fine di una
#: lettera e l'inizio della successiva ci va uno spazio. Una soglia fissa non
#: va bene: lo spazio di un corpo 10 e' piu' stretto di quello di un corpo 14,
#: e con la soglia sbagliata le parole escono attaccate.
STACCO_SPAZIO_RELATIVO = 0.18
STACCO_SPAZIO_MINIMO = 0.75

#: Oltre questo stacco, sempre in frazione del corpo, non c'e' piu' uno spazio
#: ma un'altra colonna: due celle di tabella, o due blocchi affiancati.
#: Tenerli in una riga sola fa danni a valle — la riga risulta larga quanto la
#: tabella, e il bordo della cella smette di «sporgere» dal testo, cioe'
#: diventa indistinguibile da una sottolineatura. Due volte e mezzo il corpo e'
#: largo: in un testo giustificato uno spazio non arriva a tanto.
STACCO_COLONNA_RELATIVO = 2.5


class SorgenteError(ValueError):
    """Il PDF non si apre."""


def _colore_esadecimale(valore) -> str | None:
    """Il colore di un oggetto pdfplumber in `#rrggbb`."""
    if valore is None:
        return None
    if isinstance(valore, (int, float)):
        livello = int(max(0.0, min(1.0, float(valore))) * 255)
        terna = (livello, livello, livello)
    elif isinstance(valore, (tuple, list)):
        numeri = [float(v) for v in valore]
        if len(numeri) == 1:
            livello = int(max(0.0, min(1.0, numeri[0])) * 255)
            terna = (livello, livello, livello)
        elif len(numeri) == 3:
            terna = tuple(int(max(0.0, min(1.0, v)) * 255) for v in numeri)
        elif len(numeri) == 4:  # CMYK
            c, m, y, k = (max(0.0, min(1.0, v)) for v in numeri)
            terna = (
                int(255 * (1 - c) * (1 - k)),
                int(255 * (1 - m) * (1 - k)),
                int(255 * (1 - y) * (1 - k)),
            )
        else:
            return None
    else:
        return None
    return f"#{terna[0]:02x}{terna[1]:02x}{terna[2]:02x}"


def _colore_intero(valore) -> int:
    """Il colore del testo come lo scriveva PyMuPDF: un intero 0xRRGGBB."""
    esadecimale = _colore_esadecimale(valore)
    if not esadecimale:
        return 0
    return int(esadecimale[1:], 16)


#: I bit del campo `Flags` del descrittore, come li scrive il PDF.
_FLAG_PASSO_FISSO = 1 << 0
_FLAG_GRAZIE = 1 << 1
_FLAG_CORSIVO = 1 << 6
_FLAG_GRASSETTO_FORZATO = 1 << 18

#: Da questo peso in su il carattere e' un neretto (400 e' il tondo).
PESO_GRASSETTO = 600


def stile_dal_descrittore(descrittore: dict) -> int:
    """Lo stile che il documento **dichiara** per un carattere.

    Il nome non basta. «Times New Roman,Bold» lo dice, ma un PDF scritto da un
    software giudiziario chiama i suoi caratteri `F1`, `F2`, `F3`, e allora dal
    nome non si ricava niente: il corsivo di un nome di parte spariva. Il
    descrittore invece lo dice sempre — l'inclinazione, il peso, i bit di
    `Flags` — ed e' quello che PyMuPDF leggeva.
    """
    if not descrittore:
        return 0
    bit = 0
    try:
        bandiere = int(descrittore.get("Flags") or 0)
    except (TypeError, ValueError):
        bandiere = 0
    if bandiere & _FLAG_PASSO_FISSO:
        bit |= MONO
    if bandiere & _FLAG_GRAZIE:
        bit |= GRAZIE
    if bandiere & _FLAG_CORSIVO:
        bit |= CORSIVO
    if bandiere & _FLAG_GRASSETTO_FORZATO:
        bit |= GRASSETTO
    try:
        if abs(float(descrittore.get("ItalicAngle") or 0)) > 0.5:
            bit |= CORSIVO
    except (TypeError, ValueError):
        pass
    try:
        if float(descrittore.get("FontWeight") or 0) >= PESO_GRASSETTO:
            bit |= GRASSETTO
    except (TypeError, ValueError):
        pass
    return bit


#: I bit di `macStyle`, nella tabella `head` di un carattere TrueType.
_MACSTYLE_GRASSETTO = 1 << 0
_MACSTYLE_CORSIVO = 1 << 1


def stile_dal_programma(dati: bytes) -> int:
    """Lo stile scritto dentro il carattere incorporato.

    E' l'ultima parola, e spesso l'unica. Un PDF rifatto da un convertitore
    chiama i suoi caratteri `CIDFont+F1`, `F2`, `F3` e svuota il descrittore:
    niente inclinazione, niente peso. Il nome non dice niente, il descrittore
    nemmeno — ma il carattere se lo porta scritto dentro, nella tabella `head`,
    e li' si legge che `F2` e' il neretto corsivo con cui sono scritti i nomi
    delle parti.
    """
    if not dati or len(dati) < 12:
        return 0
    try:
        quante = struct.unpack(">H", dati[4:6])[0]
        for indice in range(min(quante, 64)):
            posto = 12 + indice * 16
            if posto + 16 > len(dati):
                break
            if dati[posto:posto + 4] != b"head":
                continue
            inizio = struct.unpack(">I", dati[posto + 8:posto + 12])[0]
            if inizio + 46 > len(dati):
                return 0
            macchia = struct.unpack(">H", dati[inizio + 44:inizio + 46])[0]
            bit = 0
            if macchia & _MACSTYLE_GRASSETTO:
                bit |= GRASSETTO
            if macchia & _MACSTYLE_CORSIVO:
                bit |= CORSIVO
            return bit
    except Exception:
        return 0
    return 0


def _flag(nome_carattere: str, *, apice: bool = False, dichiarato: int = 0) -> int:
    """I bit di stile del carattere: quelli dichiarati, piu' quelli nel nome.

    Il descrittore ha la precedenza perche' e' quello che il documento afferma;
    il nome resta come rinforzo, per i PDF che il descrittore non ce l'hanno.
    """
    minuscolo = (nome_carattere or "").lower()
    bit = dichiarato
    if apice:
        bit |= APICE
    if "italic" in minuscolo or "oblique" in minuscolo:
        bit |= CORSIVO
    if "times" in minuscolo or "serif" in minuscolo or "roman" in minuscolo or "georgia" in minuscolo:
        bit |= GRAZIE
    if "mono" in minuscolo or "courier" in minuscolo:
        bit |= MONO
    if "bold" in minuscolo or "black" in minuscolo or "heavy" in minuscolo:
        bit |= GRASSETTO
    return bit


def _base_carattere(carattere: dict, altezza_pagina: float) -> float:
    """La quota della linea di base, contata dall'alto come il resto."""
    matrice = carattere.get("matrix")
    if matrice and len(matrice) >= 6:
        return altezza_pagina - float(matrice[5])
    return float(carattere.get("bottom", 0.0))


def _firma(carattere: dict) -> tuple:
    """Cosa rende due caratteri parte dello stesso span."""
    return (
        carattere.get("fontname"),
        round(float(carattere.get("size") or 0), 1),
        _colore_esadecimale(carattere.get("non_stroking_color")),
        bool(carattere.get("upright", True)),
    )


#: Segno che pdfplumber ha visto uno spazio prima di questa lettera. Non e'
#: una misura: e' quello che ha letto la sua segmentazione delle parole, e
#: batte qualunque soglia geometrica.
SPAZIO_DICHIARATO = "_iu_spazio_prima"


def _segna_gli_spazi(testo: str, caratteri: list[dict]) -> None:
    """Segna, su ogni lettera, se nel testo della riga era preceduta da spazio.

    pdfplumber la riga la legge giusta — «Patrocinante in Cassazione» — ma la
    lista delle lettere che restituisce gli spazi non li contiene: ricostruendo
    il testo da li' le parole escono attaccate. Di solito lo spazio si ritrova
    dal vuoto fra una lettera e l'altra, ma non sempre si puo': in un carattere
    calligrafico i riquadri delle lettere si **sovrappongono** di cinque punti,
    e allora un vuoto non c'e' da nessuna parte.

    Si ripercorrono testo e lettere insieme. Se non si allineano non si segna
    niente e decide la geometria: meglio nessuno spazio che uno inventato.
    """
    if not testo or not caratteri:
        return
    segni: list[bool] = []
    posto = 0
    for carattere in caratteri:
        lettera = str(carattere.get("text") or "")
        vuoti = 0
        while posto < len(testo) and testo[posto].isspace():
            vuoti += 1
            posto += 1
        if posto >= len(testo) or testo[posto] != lettera[:1]:
            return
        posto += len(lettera)
        segni.append(bool(vuoti))
    for carattere, segno in zip(caratteri, segni):
        if segno:
            carattere[SPAZIO_DICHIARATO] = True


def _con_spazi(caratteri: list[dict]) -> list[dict]:
    """Rimette gli spazi fra i caratteri di una riga.

    pdfplumber consegna le lettere disegnate, e nei PDF lo spazio quasi mai e'
    una lettera: e' il punto in cui la successiva riparte piu' in la'. Senza
    questo passaggio il testo esce tutto attaccato.

    Dove `_segna_gli_spazi` ha lasciato il suo segno non si guarda il vuoto: lo
    spazio c'era, anche se le lettere si sovrappongono.
    """
    if not caratteri:
        return []
    fuori = [caratteri[0]]
    for carattere in caratteri[1:]:
        precedente = fuori[-1]
        stacco = float(carattere["x0"]) - float(precedente["x1"])
        corpo = float(carattere.get("size") or precedente.get("size") or 11.0)
        soglia = max(corpo * STACCO_SPAZIO_RELATIVO, STACCO_SPAZIO_MINIMO)
        dichiarato = bool(carattere.get(SPAZIO_DICHIARATO))
        if (dichiarato or stacco > soglia) and str(precedente["text"]) != " ":
            estremi = sorted((float(precedente["x1"]), float(carattere["x0"])))
            spazio = dict(precedente)
            spazio["text"] = " "
            spazio["x0"], spazio["x1"] = estremi
            spazio.pop(SPAZIO_DICHIARATO, None)
            fuori.append(spazio)
        fuori.append(carattere)
    return fuori


def _separa_colonne(caratteri: list[dict]) -> list[list[dict]]:
    """Spezza una riga dove il testo salta in un'altra colonna.

    pdfplumber mette sulla stessa riga tutto quello che sta alla stessa
    altezza, comprese due celle di tabella lontane fra loro. PyMuPDF le teneva
    separate, e il codice a valle ci conta: misura quanto un filetto sporge
    oltre il testo per decidere se e' una sottolineatura o il bordo di una
    cella. Con la riga larga quanto tutta la tabella quel confronto si
    capovolge e ogni cella esce sottolineata.
    """
    if not caratteri:
        return []
    pezzi: list[list[dict]] = [[caratteri[0]]]
    for carattere in caratteri[1:]:
        precedente = pezzi[-1][-1]
        corpo = float(carattere.get("size") or precedente.get("size") or 11.0)
        stacco = float(carattere["x0"]) - float(precedente["x1"])
        if stacco > corpo * STACCO_COLONNA_RELATIVO:
            pezzi.append([carattere])
        else:
            pezzi[-1].append(carattere)
    return pezzi


@dataclass(frozen=True)
class PaginaSorgente:
    """Una pagina, con quello che serviva a `documento_fedele`."""

    numero: int
    _pagina: object
    _documento_grafico: object

    # -- misure -------------------------------------------------------------

    @property
    def larghezza(self) -> float:
        return float(self._pagina.width)

    @property
    def altezza(self) -> float:
        return float(self._pagina.height)

    @property
    def rotazione(self) -> int:
        return int(self._pagina.rotation or 0)

    @property
    def riquadro(self) -> Riquadro:
        return Riquadro(0.0, 0.0, self.larghezza, self.altezza)

    #: Il nome che aveva in PyMuPDF. Tenerlo evita di riscrivere le decine di
    #: `pagina.rect.width` sparse nel pacchetto.
    @property
    def rect(self) -> Riquadro:
        return self.riquadro

    # -- cosa c'e' disegnato ------------------------------------------------

    @property
    def rettangoli(self) -> list[dict]:
        """I rettangoli disegnati sulla pagina, pieni o solo bordati."""
        return list(self._pagina.rects or [])

    @property
    def linee(self) -> list[dict]:
        """Le linee disegnate sulla pagina."""
        return list(self._pagina.lines or [])

    @property
    def caratteri(self) -> list[dict]:
        """Tutte le lettere della pagina, con posizione e carattere."""
        return list(self._pagina.chars or [])

    @property
    def curve(self) -> list[dict]:
        """I tracciati curvi: archi, cerchi, la parte tonda di un timbro."""
        return list(self._pagina.curves or [])

    @property
    def disegni(self) -> list[dict]:
        """Tutto quello che e' disegnato e non e' testo.

        PyMuPDF li dava insieme con `get_drawings()`; pdfplumber li tiene
        divisi per tipo, quindi qui si rimettono insieme.
        """
        return self.rettangoli + self.linee + self.curve

    @property
    def immagini(self) -> list[dict]:
        """Le immagini incorporate, con il loro riquadro sulla pagina."""
        return list(self._pagina.images or [])

    @property
    def campi_modulo(self) -> list[Riquadro]:
        """I riquadri dei campi compilabili.

        La cornice di un campo modulo e' solo il vestito grafico del campo, e
        la scritta dentro viene gia' letta come testo: rasterizzarla
        raddoppierebbe ogni etichetta.
        """
        fuori: list[Riquadro] = []
        for annotazione in getattr(self._pagina, "annots", []) or []:
            dati = annotazione.get("data") or {}
            if str(dati.get("Subtype") or "").strip("/'") != "Widget":
                continue
            try:
                fuori.append(Riquadro(
                    annotazione["x0"], annotazione["top"],
                    annotazione["x1"], annotazione["bottom"],
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return fuori

    def tabelle(self, strategia: str = "lines_strict") -> list:
        """Le tabelle trovate sulla pagina, con la strategia indicata.

        Le strategie hanno i nomi di pdfplumber: `lines_strict` si fida solo
        dei filetti disegnati, `text` deduce la griglia dall'incolonnamento.
        Si prova la prima e, se non trova niente, la seconda: una tabella senza
        filetti resta una tabella.
        """
        try:
            return self._pagina.find_tables({
                "vertical_strategy": strategia,
                "horizontal_strategy": strategia,
            }) or []
        except Exception:
            return []

    @property
    def collegamenti(self) -> list[tuple[Riquadro, str]]:
        fuori: list[tuple[Riquadro, str]] = []
        for legame in getattr(self._pagina, "hyperlinks", []) or []:
            indirizzo = legame.get("uri")
            if not indirizzo:
                continue
            fuori.append((
                Riquadro(legame["x0"], legame["top"], legame["x1"], legame["bottom"]),
                str(indirizzo),
            ))
        return fuori

    @property
    def filetti(self) -> list[tuple[float, float, float]]:
        """Linee orizzontali sottili: `(x0, x1, y)`.

        Nel PDF una sottolineatura non e' un attributo del testo, e' una linea
        disegnata sotto le lettere — e lo sono anche i bordi di una tabella.
        Qui si raccolgono entrambe: distinguerle tocca a chi legge il testo.
        """
        fuori: list[tuple[float, float, float]] = []
        for elemento in list(self._pagina.lines or []) + list(self._pagina.rects or []):
            alto = float(elemento.get("top", 0.0))
            basso = float(elemento.get("bottom", 0.0))
            sinistro = float(elemento.get("x0", 0.0))
            destro = float(elemento.get("x1", 0.0))
            if abs(basso - alto) > FILETTO_ALTEZZA_MASSIMA:
                continue
            if abs(destro - sinistro) <= FILETTO_LARGHEZZA_MINIMA:
                continue
            fuori.append((sinistro, destro, (alto + basso) / 2))
        return fuori

    @property
    def evidenziature(self) -> list[tuple[Riquadro, str]]:
        """Rettangoli pieni e chiari dietro il testo."""
        fuori: list[tuple[Riquadro, str]] = []
        for rettangolo in self._pagina.rects or []:
            if not rettangolo.get("fill"):
                continue
            colore = _colore_esadecimale(rettangolo.get("non_stroking_color"))
            if not colore or colore.lower() in BIANCHI:
                continue
            riquadro = Riquadro(
                rettangolo["x0"], rettangolo["top"], rettangolo["x1"], rettangolo["bottom"]
            )
            if (
                EVIDENZIATURA_ALTEZZA_MINIMA < riquadro.height < EVIDENZIATURA_ALTEZZA_MASSIMA
                and riquadro.width > EVIDENZIATURA_LARGHEZZA_MINIMA
            ):
                fuori.append((riquadro, colore))
        return fuori

    # -- il testo -----------------------------------------------------------

    def righe_grezze(self) -> list[dict]:
        """Le righe della pagina, ognuna con i suoi span.

        La forma e' quella che PyMuPDF restituiva: ogni riga ha `bbox` e
        `spans`, ogni span ha `text`, `bbox`, `size`, `font`, `flags`, `color`,
        `origin` e `chars`.
        """
        try:
            righe = self._pagina.extract_text_lines(return_chars=True)
        except Exception:
            return []

        fuori: list[dict] = []
        for riga in righe:
            caratteri = [c for c in (riga.get("chars") or []) if c.get("text")]
            if not caratteri:
                continue
            # prima di spezzare le colonne, perche' il testo della riga le
            # attraversa e l'allineamento si fa una volta sola
            _segna_gli_spazi(str(riga.get("text") or ""), caratteri)
            for pezzo in _separa_colonne(caratteri):
                span = self._span_da_caratteri(pezzo)
                if not span:
                    continue
                fuori.append({
                    "bbox": (
                        min(float(c["x0"]) for c in pezzo),
                        min(float(c["top"]) for c in pezzo),
                        max(float(c["x1"]) for c in pezzo),
                        max(float(c["bottom"]) for c in pezzo),
                    ),
                    "spans": span,
                })
        return fuori

    @property
    def stili_dichiarati(self) -> dict:
        """Lo stile che la pagina dichiara per ognuno dei suoi caratteri."""
        try:
            from pdfminer.pdftypes import resolve1
        except Exception:
            return {}
        fuori: dict = {}
        try:
            risorse = resolve1(self._pagina.page_obj.resources) or {}
            caratteri = resolve1(risorse.get("Font")) or {}
        except Exception:
            return {}
        for riferimento in list(caratteri.values()):
            try:
                voce = resolve1(riferimento) or {}
                descrittore = resolve1(voce.get("FontDescriptor")) or {}
                if not descrittore and voce.get("DescendantFonts"):
                    discendenti = resolve1(voce["DescendantFonts"]) or []
                    if discendenti:
                        descrittore = resolve1(
                            (resolve1(discendenti[0]) or {}).get("FontDescriptor")
                        ) or {}
                nome = voce.get("BaseFont")
                nome = getattr(nome, "name", None) or str(nome or "")
                if not nome:
                    continue
                bit = stile_dal_descrittore(descrittore)
                if not (bit & (GRASSETTO | CORSIVO)):
                    for chiave in ("FontFile2", "FontFile3", "FontFile"):
                        flusso = descrittore.get(chiave)
                        if flusso is None:
                            continue
                        try:
                            bit |= stile_dal_programma(resolve1(flusso).get_data())
                        except Exception:
                            pass
                        break
                if bit:
                    fuori[nome] = fuori.get(nome, 0) | bit
            except Exception:
                continue
        return fuori

    def _span_da_caratteri(self, caratteri: list[dict]) -> list[dict]:
        """Raggruppa i caratteri consecutivi che condividono lo stile."""
        caratteri = _con_spazi(caratteri)
        dichiarati = self.stili_dichiarati
        corpo_riga = statistics.median([float(c.get("size") or 0) or 11.0 for c in caratteri])
        gruppi: list[list[dict]] = []
        firma_corrente = None
        for carattere in caratteri:
            firma = _firma(carattere)
            if firma != firma_corrente or not gruppi:
                gruppi.append([carattere])
                firma_corrente = firma
            else:
                gruppi[-1].append(carattere)

        fuori: list[dict] = []
        for gruppo in gruppi:
            testo = "".join(str(c["text"]) for c in gruppo)
            if not testo:
                continue
            nome_intero = str(gruppo[0].get("fontname") or "")
            nome = nome_intero
            corpo = round(statistics.median([float(c.get("size") or 0) for c in gruppo]), 1)
            alto = min(float(c["top"]) for c in gruppo)
            basso = max(float(c["bottom"]) for c in gruppo)
            base = _base_carattere(gruppo[0], self.altezza)
            apice = corpo < corpo_riga * 0.78 and base < alto + (basso - alto) * 0.72

            fuori.append({
                "text": testo,
                "bbox": (
                    min(float(c["x0"]) for c in gruppo), alto,
                    max(float(c["x1"]) for c in gruppo), basso,
                ),
                "size": corpo,
                "font": nome.split("+")[-1],
                "flags": _flag(nome, apice=apice,
                               dichiarato=dichiarati.get(nome_intero, 0)),
                "color": _colore_intero(gruppo[0].get("non_stroking_color")),
                "origin": (float(gruppo[0]["x0"]), base),
                "chars": [
                    {
                        "c": str(c["text"]),
                        "bbox": (float(c["x0"]), float(c["top"]),
                                 float(c["x1"]), float(c["bottom"])),
                    }
                    for c in gruppo
                ],
            })
        return fuori

    # -- rendering ----------------------------------------------------------

    def png(self, *, dpi: int = 150, ritaglio: Riquadro | None = None,
            trasparente: bool = False) -> bytes:
        """La pagina, o un suo ritaglio, come PNG."""
        pagina = self._documento_grafico[self.numero - 1]
        immagine = pagina.render(scale=dpi / 72.0, draw_annots=True).to_pil()
        immagine = immagine.convert("RGBA" if trasparente else "RGB")
        if ritaglio is not None:
            fattore = dpi / 72.0
            r = ritaglio.normalizzato()
            immagine = immagine.crop((
                max(0, int(r.x0 * fattore)), max(0, int(r.y0 * fattore)),
                min(immagine.width, int(r.x1 * fattore) + 1),
                min(immagine.height, int(r.y1 * fattore) + 1),
            ))
        fuori = io.BytesIO()
        immagine.save(fuori, format="PNG")
        return fuori.getvalue()


class DocumentoSorgente:
    """Il PDF aperto due volte: per leggerlo e per disegnarlo.

    Si usa come gestore di contesto; chiudendolo si chiudono entrambe le
    letture.
    """

    def __init__(self, origine: bytes | str | Path) -> None:
        dati = Path(origine).read_bytes() if not isinstance(origine, bytes) else origine
        try:
            self._testo = pdfplumber.open(io.BytesIO(dati))
            self._grafica = pdfium.PdfDocument(dati)
        except Exception as errore:
            raise SorgenteError("PDF illeggibile") from errore

    def __enter__(self) -> DocumentoSorgente:
        return self

    def __exit__(self, *_) -> None:
        self.chiudi()

    def chiudi(self) -> None:
        for aperto in (getattr(self, "_testo", None), getattr(self, "_grafica", None)):
            try:
                aperto.close()
            except Exception:
                pass

    #: `chiudi()` ha il nome italiano del resto del pacchetto; `close()` e'
    #: quello che il codice chiamava quando sotto c'era PyMuPDF.
    close = chiudi

    def __len__(self) -> int:
        return len(self._testo.pages)

    def __getitem__(self, indice: int) -> PaginaSorgente:
        pagina = self._testo.pages[indice]
        return PaginaSorgente(
            numero=indice + 1 if indice >= 0 else len(self) + indice + 1,
            _pagina=pagina, _documento_grafico=self._grafica,
        )

    def __iter__(self):
        return iter(self.pagine)

    @property
    def pagine(self) -> list[PaginaSorgente]:
        return [
            PaginaSorgente(numero=indice + 1, _pagina=pagina, _documento_grafico=self._grafica)
            for indice, pagina in enumerate(self._testo.pages)
        ]
