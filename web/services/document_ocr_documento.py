"""Riconoscimento del testo di un documento intero, una pagina alla volta.

Un atto che arriva allo studio non e' quasi mai una foto singola: e' un PDF di
piu' pagine, a volte gia' nativo digitale (deposito telematico, copia di
cortesia), a volte una scansione, spesso un misto delle due cose perche' alla
memoria nativa e' stato allegato un documento scansionato.

Per questo il riconoscimento non passa dal motore OCR a occhi chiusi: se la
pagina ha gia' un livello di testo lo si legge com'e' — e' il testo esatto
dell'autore, non una lettura probabilistica — e l'OCR resta per le sole pagine
che sono davvero immagini. Cosi' un atto nativo si legge in un istante e senza
errori di trascrizione, e una scansione paga il costo dell'OCR solo dove serve.

La struttura (titoli, capoversi, elenchi, tabelle) si ricava in entrambi i casi
da `legal_ocr.page_layout`, a partire dalla posizione delle parole: le due
strade producono quindi lo stesso tipo di risultato e la revisione in pagina
non deve distinguerle.

Base normativa: la copia informatica per immagine di un documento analogico
resta una scansione (D.Lgs. 82/2005, art. 22); lo strato di testo aggiunto dal
riconoscimento la rende ricercabile ma non la trasforma in atto nativo digitale
(Specifiche tecniche DGSIA D.M. 44/2011, art. 15, comma 1, lett. c). Per questo
il documento originale non viene mai sostituito: la copia ricercabile, se
salvata, e' un documento in piu' nel fascicolo.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from legal_ocr.page_layout import analizza_pagina
from legal_ocr.tratti import con_tratti
from web.services.document_ocr import recognize_page
from web.services.document_ocr_anteprima import ANTEPRIMA_ASSENTE, Anteprima, anteprima_da_pdf
from web.services.document_ocr_anteprima import come_payload as anteprima_payload
from web.services.document_ocr_correzioni import correggi_blocchi
from web.services.document_ocr_formato import _colore_leggibile, blocchi_con_formato
from web.services.document_ocr_riferimenti import riferimenti_del_testo
from web.services.document_tools import DocumentToolError

# Un fascicolo puo' contenere allegati molto grandi: oltre questa soglia il
# riconoscimento non e' piu' un'operazione interattiva e va fatto altrove.
MAX_DOCUMENTO_BYTES = 120 * 1024 * 1024
MAX_PAGINE_DOCUMENTO = 500

# Densita' di rasterizzazione delle pagine senza testo: 300 dpi e' la densita'
# di riferimento delle scansioni forensi e la piu' affidabile per il motore.
DPI_RASTERIZZAZIONE = 300

# Sotto questa quantita' di caratteri il livello di testo non e' il contenuto
# della pagina ma un residuo (numero di pagina, filigrana, intestazione di un
# timbro digitale): la pagina va riconosciuta come immagine.
CARATTERI_TESTO_NATIVO_MINIMI = 80

ORIGINE_TESTO = "testo"
ORIGINE_OCR = "ocr"

ETICHETTE_ORIGINE = {
    ORIGINE_TESTO: "testo gia' presente nel documento",
    ORIGINE_OCR: "riconoscimento ottico (OCR)",
}

ESTENSIONI_IMMAGINE = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
ESTENSIONI_PDF = {".pdf"}
# Gli atti firmati arrivano come `.pdf.p7m`: la busta CAdES contiene il PDF.
ESTENSIONI_BUSTA = {".p7m"}
ESTENSIONI_RICONOSCIBILI = ESTENSIONI_IMMAGINE | ESTENSIONI_PDF | ESTENSIONI_BUSTA


@dataclass(frozen=True)
class PaginaRiconosciuta:
    """Una pagina letta: struttura, testo lineare e PDF ricercabile della pagina."""

    numero: int
    origine: str
    pdf: bytes
    paragraphs: list[str]
    blocks: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = ""
    anteprima: Anteprima = ANTEPRIMA_ASSENTE
    # Correzioni forensi applicate e riferimenti giuridici leggibili nella
    # pagina: servono all'avvocato per controllare il riconoscimento.
    correzioni: list[dict[str, Any]] = field(default_factory=list)
    riferimenti: dict[str, list[str]] = field(default_factory=dict)

    @property
    def characters(self) -> int:
        return sum(len(re.sub(r"\s+", "", paragrafo)) for paragrafo in self.paragraphs)


def riconoscibile(nome: str) -> bool:
    """Vero quando il formato e' leggibile: PDF, busta firmata o immagine."""
    return Path(str(nome or "")).suffix.lower() in ESTENSIONI_RICONOSCIBILI


def _pdf_incorporato(data: bytes) -> bytes | None:
    """PDF contenuto in una busta firmata `.p7m`, quando c'e'."""
    inizio = data.find(b"%PDF")
    if inizio < 0:
        return None
    fine = data.rfind(b"%%EOF")
    return data[inizio : fine + 5] if fine > inizio else data[inizio:]


def _sorgente_pdf(data: bytes, nome: str) -> bytes | None:
    """Byte del PDF da leggere, None quando il documento e' un'immagine."""
    suffisso = Path(str(nome or "")).suffix.lower()
    if suffisso in ESTENSIONI_IMMAGINE:
        return None
    if data[:4] == b"%PDF":
        return data
    if suffisso in ESTENSIONI_BUSTA or suffisso in ESTENSIONI_PDF:
        incorporato = _pdf_incorporato(data)
        if incorporato is None:
            raise DocumentToolError(
                "Il documento firmato non contiene un PDF leggibile: scaricalo e riprova con il file originale."
            )
        return incorporato
    if suffisso not in ESTENSIONI_RICONOSCIBILI:
        raise DocumentToolError(
            "Formato non riconoscibile: il riconoscimento del testo funziona su PDF, immagini e atti firmati .p7m."
        )
    return None


def _controlla_dimensione(data: bytes) -> None:
    if not data:
        raise DocumentToolError("Il documento da riconoscere è vuoto.")
    if len(data) > MAX_DOCUMENTO_BYTES:
        raise DocumentToolError("Il documento supera 120 MB: riconosci il testo su una porzione più piccola.")


def _apri(sorgente: bytes):
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    try:
        documento = fitz.open(stream=sorgente, filetype="pdf")
    except Exception as exc:
        raise DocumentToolError("Il PDF non è leggibile: potrebbe essere danneggiato.") from exc
    if getattr(documento, "needs_pass", False):
        documento.close()
        raise DocumentToolError("Il PDF è protetto da password: rimuovi la protezione e riprova.")
    if documento.page_count < 1:
        documento.close()
        raise DocumentToolError("Il PDF non contiene pagine da riconoscere.")
    if documento.page_count > MAX_PAGINE_DOCUMENTO:
        pagine = documento.page_count
        documento.close()
        raise DocumentToolError(
            f"Il documento ha {pagine} pagine: il riconoscimento in pagina si ferma a {MAX_PAGINE_DOCUMENTO}."
        )
    return documento


def conta_pagine(data: bytes, nome: str) -> int:
    """Numero di pagine del documento; le immagini valgono una pagina."""
    _controlla_dimensione(data)
    sorgente = _sorgente_pdf(data, nome)
    if sorgente is None:
        return 1
    documento = _apri(sorgente)
    try:
        return int(documento.page_count)
    finally:
        documento.close()


def _stile_span(span: dict[str, Any]) -> tuple[bool, bool]:
    """Grassetto e corsivo dichiarati dal PDF per quel pezzo di riga.

    PyMuPDF espone sia i flag del carattere (bit 4 grassetto, bit 1 corsivo) sia
    il nome del font: i due si controllano insieme perche' molti PDF prodotti da
    Word dichiarano lo stile solo nel nome ("TimesNewRoman-Bold").
    """
    bandiere = int(span.get("flags") or 0)
    nome = str(span.get("font") or "").lower()
    grassetto = bool(bandiere & 16) or "bold" in nome or "black" in nome or "heavy" in nome
    corsivo = bool(bandiere & 2) or "italic" in nome or "oblique" in nome
    return grassetto, corsivo


def _colore_span(span: dict[str, Any]) -> str:
    """Il colore dichiarato dal PDF per questo pezzo di riga.

    PyMuPDF lo consegna come numero intero sRGB. Passa dallo stesso vaglio del
    colore misurato sulle scansioni: il nero di un atto non si dichiara, si
    lascia al documento, altrimenti ogni capoverso si porterebbe dietro un
    «#000000» che non aggiunge niente e che poi qualcuno dovrebbe togliere.
    """
    try:
        valore = int(span.get("color") or 0)
    except (TypeError, ValueError):
        return ""
    if valore < 0 or valore > 0xFFFFFF:
        return ""
    return _colore_leggibile((valore >> 16) & 0xFF, (valore >> 8) & 0xFF, valore & 0xFF)


def _famiglia_span(span: dict[str, Any]) -> str:
    """Il carattere dello span, ricondotto a una famiglia che l'editor offre.

    La corrispondenza e' quella dell'importazione fedele: lo stesso PDF deve
    dare lo stesso carattere che lo si apra nell'editor o che lo si passi dal
    riconoscimento. «ABCDEF+TimesNewRomanPS-BoldMT» diventa «Times New Roman».
    """
    return _famiglia_del_font(str(span.get("font") or "").strip())


@lru_cache(maxsize=256)
def _famiglia_del_font(nome: str) -> str:
    # Una pagina ha centinaia di span e quasi sempre tre o quattro caratteri.
    if not nome:
        return ""
    try:
        from pct.documento_fedele.taratura import famiglia_editor
    except Exception:  # pragma: no cover - solo se l'importazione fedele manca
        return ""
    try:
        return famiglia_editor(nome)[0]
    except Exception:
        return ""


def _filetti_della_pagina(sorgente: bytes, indice: int) -> list[tuple[float, float, float]]:
    """Le linee orizzontali sottili della pagina, lette come le legge l'analizzatore.

    Nel PDF una sottolineatura non e' un attributo del testo: e' una linea
    disegnata sotto le lettere, come i bordi di una tabella. L'importazione
    fedele sa gia' distinguere le une dagli altri; qui si usa la stessa lettura,
    cosi' lo stesso PDF da' le stesse sottolineature da tutte e due le strade.
    Se la lettura non riesce la pagina si legge lo stesso, senza decorazioni.
    """
    try:
        from pct.documento_fedele.sorgente import DocumentoSorgente

        with DocumentoSorgente(sorgente) as documento:
            return list(documento[indice].filetti)
    except Exception:
        return []


def _decorazioni_parola(
    parola: tuple[float, float, float, float],
    span: tuple[float, float, float, float],
    filetti: Sequence[tuple[float, float, float]],
) -> tuple[bool, bool]:
    """(sottolineato, barrato) di una parola, con la regola dell'analizzatore.

    La sporgenza della linea si misura sullo span e non sulla parola: una
    sottolineatura che copre tre parole sporge da ciascuna, ma non dallo span.
    """
    if not filetti:
        return False, False
    try:
        from pct.documento_fedele.geometria import Riquadro
        from pct.documento_fedele.lettura import _decorazioni

        return _decorazioni(Riquadro(parola), list(filetti), Riquadro(span))
    except Exception:
        return False, False


def _parole_dello_span(
    span: dict[str, Any],
    scala: float,
    blocco: int,
    riga: int,
    indice: int,
    filetti: Sequence[tuple[float, float, float]] = (),
) -> list[dict[str, Any]]:
    """Parole di uno span, nella stessa forma che produce il motore OCR.

    Il PDF descrive pezzi di riga, non parole: la riga viene divisa sugli spazi e
    a ogni parola si assegna la porzione di larghezza proporzionale ai suoi
    caratteri. E' un'approssimazione di pochi pixel, sufficiente per struttura e
    allineamento, mentre corpo e stile restano quelli dichiarati.
    """
    testo = str(span.get("text") or "")
    if not testo.strip():
        return []
    riquadro = span.get("bbox") or (0.0, 0.0, 0.0, 0.0)
    x0, y0, x1, y1 = (float(valore) for valore in riquadro)
    larghezza_totale = max(0.0, x1 - x0)
    caratteri = len(testo) or 1
    passo = larghezza_totale / caratteri
    grassetto, corsivo = _stile_span(span)
    corpo = float(span.get("size") or 0.0)
    colore = _colore_span(span)
    famiglia = _famiglia_span(span)
    # Per le decorazioni il riquadro si prende dalla linea di base e dal corpo,
    # con la discesa delle metriche standard (un quinto del corpo). PyMuPDF
    # allarga la discesa di alcuni caratteri base fino a un terzo: una
    # sottolineatura di Word, a un punto e mezzo sotto la base, finiva
    # «dentro» le lettere e non veniva riconosciuta.
    base = float((span.get("origin") or (0.0, y1))[1])
    alto_lettere, basso_lettere = (base - corpo * 0.8, base + corpo * 0.2) if corpo > 0 else (y0, y1)

    # Con i caratteri (rawdict) ogni parola ha il suo riquadro esatto; senza,
    # la larghezza della riga si divide in parti uguali per carattere.
    caratteri = span.get("chars") or []
    esatti = len(caratteri) == len(testo)
    parole: list[dict[str, Any]] = []
    posizione = 0
    for pezzo in testo.split(" "):
        if pezzo.strip():
            inizio = x0 + posizione * passo
            fine = inizio + len(pezzo) * passo
            if esatti:
                primo = posizione + (len(pezzo) - len(pezzo.lstrip()))
                ultimo = posizione + len(pezzo.rstrip()) - 1
                inizio = float(caratteri[primo]["bbox"][0])
                fine = max(inizio + 0.1, float(caratteri[ultimo]["bbox"][2]))
            sottolineato, barrato = _decorazioni_parola(
                (inizio, alto_lettere, fine, basso_lettere), (x0, alto_lettere, x1, basso_lettere), filetti
            )
            parole.append(
                {
                    "text": pezzo.strip(),
                    "left": round(inizio * scala),
                    "top": round(y0 * scala),
                    "width": max(1, round((fine - inizio) * scala)),
                    "height": max(1, round((y1 - y0) * scala)),
                    # Il testo dell'autore non e' una lettura probabilistica.
                    "conf": 1.0,
                    "block": blocco + 1,
                    "par": blocco + 1,
                    "line": riga + 1,
                    "word": indice + len(parole) + 1,
                    # Formato dichiarato dal documento: prevale su ogni stima.
                    "corpo": corpo,
                    "grassetto": grassetto,
                    "corsivo": corsivo,
                    "colore": colore,
                    "famiglia": famiglia,
                    "sottolineato": sottolineato,
                    "barrato": barrato,
                }
            )
        posizione += len(pezzo) + 1
    return parole


#: Fra due pezzi della stessa parola non c'e' distanza: una parola che cambia
#: stile a meta' (Word mette «nio» in corsivo dentro «Antonio») arriva dal PDF
#: in due span attaccati. Uno spazio vero misura un quarto del corpo.
DISTANZA_DENTRO_LA_PAROLA = 0.1
#: Un pezzo molto piu' piccolo attaccato a una parola e' un apice (il rimando
#: a una nota), non il seguito della parola.
RAPPORTO_CORPO_STESSA_PAROLA = 0.8


def _continua_la_parola(prima: dict[str, Any], dopo: dict[str, Any]) -> bool:
    """Vero se lo span `dopo` prosegue l'ultima parola dello span `prima`."""
    testo_prima = str(prima.get("text") or "")
    testo_dopo = str(dopo.get("text") or "")
    if not testo_prima or not testo_dopo or testo_prima[-1].isspace() or testo_dopo[0].isspace():
        return False
    corpo_prima = float(prima.get("size") or 0.0)
    corpo_dopo = float(dopo.get("size") or 0.0)
    corpo = max(corpo_prima, corpo_dopo, 1.0)
    if min(corpo_prima, corpo_dopo) < corpo * RAPPORTO_CORPO_STESSA_PAROLA:
        return False
    try:
        distanza = float(dopo["bbox"][0]) - float(prima["bbox"][2])
    except (KeyError, IndexError, TypeError, ValueError):
        return False
    return -corpo * 0.2 <= distanza <= corpo * DISTANZA_DENTRO_LA_PAROLA


def _unisci_parole(prima: dict[str, Any], dopo: dict[str, Any]) -> dict[str, Any]:
    """Una parola sola dai due pezzi: il formato e' quello del pezzo piu' lungo.

    Il formato dentro una parola non passa (i tratti sono fatti di parole), ma
    il testo si': nell'atto deve esserci «Antonio», non «Anto nio».
    """
    sinistra = min(float(prima["left"]), float(dopo["left"]))
    destra = max(float(prima["left"]) + float(prima["width"]), float(dopo["left"]) + float(dopo["width"]))
    alto = min(float(prima["top"]), float(dopo["top"]))
    basso = max(float(prima["top"]) + float(prima["height"]), float(dopo["top"]) + float(dopo["height"]))
    prevalente = dopo if len(str(dopo.get("text") or "")) > len(str(prima.get("text") or "")) else prima
    fuori = dict(prima)
    fuori.update(
        text=f"{prima.get('text') or ''}{dopo.get('text') or ''}",
        left=round(sinistra),
        top=round(alto),
        width=max(1, round(destra - sinistra)),
        height=max(1, round(basso - alto)),
    )
    for chiave in ("corpo", "grassetto", "corsivo", "colore", "famiglia", "sottolineato", "barrato"):
        if chiave in prevalente:
            fuori[chiave] = prevalente[chiave]
    return fuori


def _parole_native(
    pagina, scala: float, filetti: Sequence[tuple[float, float, float]] = ()
) -> list[dict[str, Any]]:
    """Parole del livello di testo, con corpo e stile dichiarati dal PDF.

    Le coordinate del PDF sono in punti tipografici: vengono portate alla scala
    dei pixel usata dall'OCR perche' l'analisi della struttura ragiona su
    larghezze di carattere e distanze fra righe.
    """
    try:
        # `sort=True`: i blocchi arrivano in ordine di lettura e non nell'ordine
        # in cui il PDF li ha scritti. Senza, un atto composto da piu' oggetti di
        # testo (le formule di chiusura, le firme) si ricostruisce alla rovescia.
        contenuto = pagina.get_text("rawdict", sort=True) or {}
        for blocco in contenuto.get("blocks") or []:
            for riga in blocco.get("lines") or []:
                for span in riga.get("spans") or []:
                    if "text" not in span:
                        span["text"] = "".join(str(carattere.get("c") or "") for carattere in span.get("chars") or [])
    except Exception:
        contenuto = {}
    parole: list[dict[str, Any]] = []
    for numero_blocco, blocco in enumerate(contenuto.get("blocks") or []):
        for numero_riga, riga in enumerate(blocco.get("lines") or []):
            precedente: dict[str, Any] | None = None
            for span in riga.get("spans") or []:
                nuove = _parole_dello_span(span, scala, numero_blocco, numero_riga, len(parole), filetti)
                # una parola divisa in due span non diventa due parole
                if nuove and parole and precedente is not None and _continua_la_parola(precedente, span):
                    parole[-1] = _unisci_parole(parole[-1], nuove[0])
                    nuove = nuove[1:]
                parole.extend(nuove)
                if str(span.get("text") or "").strip():
                    precedente = span
    if parole:
        return parole
    # Un PDF senza struttura dichiarata (raro, ma capita nei tracciati vecchi)
    # espone comunque le parole: meglio senza formato che senza testo.
    for voce in pagina.get_text("words") or []:
        if len(voce) < 8:
            continue
        x0, y0, x1, y1, testo, blocco, riga, indice = voce[:8]
        pulito = str(testo or "").strip()
        if not pulito:
            continue
        parole.append(
            {
                "text": pulito,
                "left": round(float(x0) * scala),
                "top": round(float(y0) * scala),
                "width": max(1, round((float(x1) - float(x0)) * scala)),
                "height": max(1, round((float(y1) - float(y0)) * scala)),
                "conf": 1.0,
                "block": int(blocco) + 1,
                "par": int(blocco) + 1,
                "line": int(riga) + 1,
                "word": int(indice) + 1,
            }
        )
    return parole


def _pagina_pdf(documento, indice: int) -> bytes:
    """La singola pagina come PDF autonomo, conservata com'era nell'originale."""
    import fitz  # type: ignore

    estratto = fitz.open()
    try:
        estratto.insert_pdf(documento, from_page=indice, to_page=indice)
        return bytes(estratto.tobytes())
    finally:
        estratto.close()


def _immagine_pagina(pagina) -> bytes:
    import fitz  # type: ignore

    scala = DPI_RASTERIZZAZIONE / 72.0
    try:
        pixmap = pagina.get_pixmap(matrix=fitz.Matrix(scala, scala), alpha=False)
        return bytes(pixmap.tobytes("png"))
    except Exception as exc:
        raise DocumentToolError("La pagina non è stata convertita in immagine: riprova.") from exc


def _caratteri(parole: list[dict[str, Any]]) -> int:
    return sum(len(str(parola.get("text") or "")) for parola in parole)


def _paragrafi(blocchi: Sequence[dict[str, Any]]) -> list[str]:
    """Testo lineare dei blocchi gia' corretti, con le tabelle riga per riga."""
    paragrafi: list[str] = []
    for blocco in blocchi:
        if blocco.get("tipo") == "tabella":
            paragrafi.extend(
                " | ".join(str(cella) for cella in riga) for riga in blocco.get("righe") or [] if any(riga)
            )
        elif blocco.get("testo"):
            paragrafi.append(str(blocco["testo"]))
    return paragrafi


def _rifinisci(blocchi: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], list[dict[str, Any]], dict[str, list[str]]]:
    """Applica le correzioni forensi e legge i riferimenti giuridici della pagina.

    Le due cose stanno insieme perche' i riferimenti vanno cercati nel testo
    gia' normalizzato: un numero di ruolo spezzato dagli spazi dell'OCR non
    verrebbe riconosciuto prima della correzione.
    """
    corretti, applicate = correggi_blocchi(blocchi)
    paragrafi = _paragrafi(corretti)
    return corretti, paragrafi, applicate, riferimenti_del_testo("\n".join(paragrafi))


def riconosci_pagina(
    data: bytes,
    nome: str,
    numero: int = 1,
    *,
    raddrizza: bool = True,
) -> PaginaRiconosciuta:
    """Legge la pagina richiesta: testo nativo quando c'e', OCR quando manca."""
    _controlla_dimensione(data)
    if numero < 1:
        raise DocumentToolError("Numero di pagina non valido.")
    sorgente = _sorgente_pdf(data, nome)

    if sorgente is None:
        if numero != 1:
            raise DocumentToolError("Questa immagine ha una sola pagina.")
        esito = recognize_page(data, 0, raddrizza=raddrizza)
        blocks, paragrafi, correzioni, riferimenti = _rifinisci(esito.blocks)
        return PaginaRiconosciuta(
            numero=1,
            origine=ORIGINE_OCR,
            pdf=esito.pdf,
            paragraphs=paragrafi,
            blocks=blocks,
            figures=list(esito.figures),
            confidence=esito.confidence,
            engine=esito.engine,
            anteprima=esito.anteprima,
            correzioni=correzioni,
            riferimenti=riferimenti,
        )

    documento = _apri(sorgente)
    try:
        if numero > documento.page_count:
            raise DocumentToolError(f"Il documento ha {documento.page_count} pagine.")
        indice = numero - 1
        pagina = documento.load_page(indice)
        parole = _parole_native(pagina, DPI_RASTERIZZAZIONE / 72.0)
        if _caratteri(parole) >= CARATTERI_TESTO_NATIVO_MINIMI:
            filetti = _filetti_della_pagina(sorgente, indice)
            if filetti:
                # si rileggono le parole con le linee: solo ora si sa che la pagina e' di testo
                parole = _parole_native(pagina, DPI_RASTERIZZAZIONE / 72.0, filetti)
            blocchi = analizza_pagina(parole, pagina=numero)
            blocks, paragrafi, correzioni, riferimenti = _rifinisci(blocchi_con_formato(blocchi, parole))
            # I tratti si fanno sul testo gia' corretto: le parole si
            # riabbinano per contenuto, non per posizione.
            blocks = con_tratti(blocks, parole)
            return PaginaRiconosciuta(
                numero=numero,
                origine=ORIGINE_TESTO,
                pdf=_pagina_pdf(documento, indice),
                paragraphs=paragrafi,
                blocks=blocks,
                figures=[],
                confidence=1.0,
                engine="testo del documento",
                anteprima=anteprima_da_pdf(pagina, DPI_RASTERIZZAZIONE / 72.0),
                correzioni=correzioni,
                riferimenti=riferimenti,
            )
        immagine = _immagine_pagina(pagina)
    finally:
        documento.close()

    esito = recognize_page(immagine, 0, raddrizza=raddrizza)
    blocks, paragrafi, correzioni, riferimenti = _rifinisci(esito.blocks)
    return PaginaRiconosciuta(
        numero=numero,
        origine=ORIGINE_OCR,
        pdf=esito.pdf,
        paragraphs=paragrafi,
        blocks=blocks,
        figures=list(esito.figures),
        confidence=esito.confidence,
        engine=esito.engine,
        anteprima=esito.anteprima,
        correzioni=correzioni,
        riferimenti=riferimenti,
    )


def come_payload(pagina: PaginaRiconosciuta) -> dict[str, Any]:
    """Pagina riconosciuta nella forma attesa dalla pagina React."""
    return {
        "numero": pagina.numero,
        "origine": pagina.origine,
        "origine_etichetta": ETICHETTE_ORIGINE.get(pagina.origine, pagina.origine),
        "pdf_base64": base64.b64encode(pagina.pdf).decode("ascii"),
        "paragraphs": pagina.paragraphs,
        "characters": pagina.characters,
        "blocks": pagina.blocks,
        "figures": pagina.figures,
        "confidence": round(float(pagina.confidence), 4),
        "engine": pagina.engine,
        "anteprima": anteprima_payload(pagina.anteprima),
        "correzioni": list(pagina.correzioni),
        "riferimenti": dict(pagina.riferimenti),
    }


__all__ = [
    "CARATTERI_TESTO_NATIVO_MINIMI",
    "DPI_RASTERIZZAZIONE",
    "ESTENSIONI_RICONOSCIBILI",
    "MAX_DOCUMENTO_BYTES",
    "MAX_PAGINE_DOCUMENTO",
    "ORIGINE_OCR",
    "ORIGINE_TESTO",
    "PaginaRiconosciuta",
    "come_payload",
    "conta_pagine",
    "riconosci_pagina",
    "riconoscibile",
]
