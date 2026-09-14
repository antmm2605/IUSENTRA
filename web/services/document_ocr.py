"""Riconoscimento del testo di una pagina acquisita, per la pagina React.

Il motore e' uno solo e vive in `legal_ocr.motore`: qui si adatta il risultato
alla forma che l'editor e la pagina di acquisizione si aspettano e si traducono
gli errori nel messaggio per l'avvocato. Nessun contenuto viene persistito: il
salvataggio nel fascicolo resta un'azione esplicita.

Base normativa: la copia informatica per immagine di documento analogico
(D.Lgs. 82/2005, art. 22) resta una scansione; l'OCR aggiunge solo lo strato di
testo selezionabile e non trasforma la scansione in atto nativo digitale
(Specifiche tecniche DGSIA D.M. 44/2011, art. 15, comma 1, lett. c).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from legal_ocr.motore import CONFIGURAZIONI, ErroreLettura, parole_da_dati, riconosci_immagine
from legal_ocr.motore.immagine import densita_pagina
from legal_ocr.motore.lettura import _LINGUA_VERIFICATA, _VERIFICA, LINGUA, motore_pronto
from legal_ocr.motore.pagina import MAX_IMMAGINE_BYTES, MAX_PIXEL, paragrafi_dai_blocchi
from legal_ocr.motore.punteggio import punteggio_parole
from web.services.document_ocr_anteprima import ANTEPRIMA_ASSENTE, Anteprima, anteprima_da_immagine
from web.services.document_tools import DocumentToolError

MAX_OCR_IMAGE_BYTES = MAX_IMMAGINE_BYTES
MAX_OCR_PIXELS = MAX_PIXEL
OCR_LANGUAGE = LINGUA
CONFIDENZA_MINIMA_ACCETTABILE = 0.72

# Compatibilita' con il codice che importava questi nomi dalla versione precedente.
A4_WIDTH_INCHES = 210 / 25.4
A4_HEIGHT_INCHES = 297 / 25.4
page_dpi = densita_pagina
_LANGUAGE_READY = False


@dataclass(frozen=True)
class OcrPageResult:
    pdf: bytes
    paragraphs: list[str]
    dpi: int
    blocks: list[dict[str, Any]] = field(default_factory=list)
    figures: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    engine: str = ""
    steps: tuple[str, ...] = ()
    # Immagine della pagina da affiancare al testo: serve a controllare il
    # riconoscimento, non a conservare il documento.
    anteprima: Anteprima = ANTEPRIMA_ASSENTE
    correzioni: list[dict[str, Any]] = field(default_factory=list)
    riferimenti: dict[str, list[str]] = field(default_factory=dict)
    consenso: int = 0
    secondo_lettore: str = ""

    @property
    def characters(self) -> int:
        return sum(len(re.sub(r"\s+", "", paragraph)) for paragraph in self.paragraphs)

    @property
    def tables(self) -> int:
        return sum(1 for blocco in self.blocks if blocco.get("tipo") == "tabella")


def punteggio_lettura(parole: list[dict[str, Any]]) -> float:
    """Qualita' di una lettura: quantita' di testo pesata dalla confidenza."""
    return punteggio_parole(parole)


def _tesseract():
    """Il modulo pytesseract pronto, con il dizionario italiano verificato."""
    global _LANGUAGE_READY
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    if not _LANGUAGE_READY:
        with _VERIFICA:
            _LINGUA_VERIFICATA.pop(id(pytesseract), None)
    try:
        motore_pronto(pytesseract, lingua=OCR_LANGUAGE)
    except ErroreLettura as exc:
        raise DocumentToolError(str(exc)) from exc
    _LANGUAGE_READY = True
    return pytesseract


def _blocchi_in_paragrafi(blocchi) -> list[str]:
    """Testo lineare dei blocchi, con le tabelle rese riga per riga."""
    return paragrafi_dai_blocchi(list(blocchi))


def recognize_page(data: bytes, rotation: int = 0, *, raddrizza: bool = True) -> OcrPageResult:
    """OCR in lingua italiana di una pagina; PDF ricercabile, struttura e zone grafiche."""
    pytesseract = _tesseract()
    try:
        pagina = riconosci_immagine(data, rotazione=rotation, raddrizza=raddrizza, pytesseract=pytesseract)
    except ErroreLettura as exc:
        raise DocumentToolError(str(exc)) from exc
    try:
        anteprima = anteprima_da_immagine(pagina.immagine)
    except Exception:
        anteprima = ANTEPRIMA_ASSENTE
    finally:
        try:
            pagina.immagine.close()
        except Exception:
            pass
    return OcrPageResult(
        pdf=pagina.pdf,
        paragraphs=pagina.paragrafi,
        dpi=pagina.dpi,
        blocks=pagina.blocchi,
        figures=pagina.figure,
        confidence=pagina.confidenza,
        engine=pagina.motore,
        steps=pagina.passaggi,
        anteprima=anteprima,
        correzioni=pagina.correzioni,
        riferimenti=pagina.riferimenti,
        consenso=pagina.consenso,
        secondo_lettore=pagina.secondo_lettore,
    )


__all__ = [
    "CONFIGURAZIONI",
    "CONFIDENZA_MINIMA_ACCETTABILE",
    "MAX_OCR_IMAGE_BYTES",
    "MAX_OCR_PIXELS",
    "OCR_LANGUAGE",
    "OcrPageResult",
    "page_dpi",
    "parole_da_dati",
    "punteggio_lettura",
    "recognize_page",
]
