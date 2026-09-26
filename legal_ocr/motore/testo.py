"""Solo il testo: per l'indice di ricerca, Lex, l'editor e i lettori automatici.

Quando serve il testo e non la forma (indicizzazione, ricerca, classificazione,
assistente), la stessa lettura si riduce alle parole corrette dal formulario.
Il PDF viene letto pagina per pagina: dove c'e' un livello di testo si usa
quello, che e' il testo esatto dell'autore; il motore ottico resta per le
pagine che sono immagini.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from typing import Any

from ..formulario import applica_formulario
from .errori import ErroreLettura
from .immagine import prepara_pagina
from .lettura import LINGUA, leggi_immagine
from .pagina import _pytesseract

ORIGINE_TESTO = "testo"
ORIGINE_OCR = "ocr"
# Sotto questa quantita' di caratteri il livello di testo e' un residuo (numero
# di pagina, filigrana) e la pagina va letta come immagine.
CARATTERI_TESTO_NATIVO_MINIMI = 80
DPI_RASTERIZZAZIONE = 300


@dataclass(frozen=True)
class TestoLetto:
    testo: str
    confidenza: float
    origine: str
    motore: str = ""
    avvisi: tuple[str, ...] = ()
    correzioni: tuple[str, ...] = ()


@dataclass(frozen=True)
class PaginaTesto:
    numero: int
    testo: str
    origine: str
    confidenza: float
    avvisi: tuple[str, ...] = ()
    # Le tabelle disegnate della pagina, come struttura (righe e celle): il testo
    # resta quello dell'autore; chi vuole la forma testuale usa `testo_con_tabelle`.
    tabelle: tuple = ()

    def testo_con_tabelle(self, *, primo: int = 1) -> str:
        from ..tabelle import con_blocchi

        return con_blocchi(self.testo, self.tabelle, primo=primo)


def _testo_nativo_affidabile(testo: str) -> bool:
    pulito = str(testo or "").strip()
    if len(pulito) < CARATTERI_TESTO_NATIVO_MINIMI:
        return False
    if "(cid:" in pulito:
        return False
    alfabetici = sum(1 for carattere in pulito if carattere.isalpha())
    return alfabetici / max(1, len(pulito)) >= 0.35


def testo_da_immagine(
    immagine: Any,
    *,
    pytesseract: object | None = None,
    lingua: str = LINGUA,
    raddrizza: bool = True,
    dpi: int | None = None,
) -> TestoLetto:
    """Il testo di un'immagine PIL, letto e corretto dal formulario."""
    motore = _pytesseract(pytesseract)
    preparata = prepara_pagina(immagine, raddrizza=raddrizza)
    try:
        lettura = leggi_immagine(preparata.immagine, pytesseract=motore, lingua=lingua, dpi=dpi or preparata.dpi, con_pdf=False)
    finally:
        if preparata.immagine is not immagine:
            try:
                preparata.immagine.close()
            except Exception:
                pass
    esito = applica_formulario(lettura.testo)
    return TestoLetto(
        testo=esito.testo,
        confidenza=lettura.confidenza,
        origine=ORIGINE_OCR,
        motore=f"tesseract · lettura {lettura.configurazione}" if lettura.configurazione else "tesseract",
        avvisi=lettura.avvisi,
        correzioni=tuple(esito.regole),
    )


def testo_da_immagine_bytes(data: bytes, *, pytesseract: object | None = None, lingua: str = LINGUA) -> TestoLetto:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise ErroreLettura("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    try:
        immagine = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as exc:
        raise ErroreLettura("La pagina non è un'immagine leggibile.") from exc
    try:
        if getattr(immagine, "n_frames", 1) > 1:
            pagine: list[str] = []
            confidenze: list[float] = []
            avvisi: list[str] = []
            for indice in range(int(getattr(immagine, "n_frames", 1))):
                immagine.seek(indice)
                letto = testo_da_immagine(immagine.copy().convert("RGB"), pytesseract=pytesseract, lingua=lingua)
                pagine.append(letto.testo)
                confidenze.append(letto.confidenza)
                avvisi.extend(letto.avvisi)
            return TestoLetto("\n\n".join(p for p in pagine if p), sum(confidenze) / len(confidenze) if confidenze else 0.0, ORIGINE_OCR, "tesseract", tuple(avvisi))
        return testo_da_immagine(immagine, pytesseract=pytesseract, lingua=lingua)
    finally:
        immagine.close()


def _tabelle(pagina: Any, numero: int, testo: str) -> tuple:
    """Le tabelle disegnate di una pagina con testo nativo e almeno tre importi o date."""
    try:
        from ..tabelle import da_pymupdf, pagina_con_numeri

        return tuple(da_pymupdf(pagina, numero)) if pagina_con_numeri(testo) else ()
    except Exception:
        return ()


def _max_pagine_predefinito() -> int:
    try:
        return max(0, int(os.environ.get("IUSENTRA_DOCUMENT_AI_OCR_MAX_PAGES", "0") or 0))
    except ValueError:
        return 0


def testo_da_pdf(
    data: bytes,
    *,
    pytesseract: object | None = None,
    lingua: str = LINGUA,
    max_pagine: int | None = None,
    dpi: int = DPI_RASTERIZZAZIONE,
    solo_immagini: bool = False,
) -> list[PaginaTesto]:
    """Testo di ogni pagina del PDF: nativo dove c'e', letto dalla macchina altrove.

    `solo_immagini=True` forza la lettura ottica anche sulle pagine con testo
    (serve quando il livello di testo e' inaffidabile).
    """
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ErroreLettura("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise ErroreLettura("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    limite = _max_pagine_predefinito() if max_pagine is None else max(0, int(max_pagine))
    try:
        documento = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ErroreLettura("Il PDF non è leggibile: potrebbe essere danneggiato.") from exc
    pagine: list[PaginaTesto] = []
    try:
        if getattr(documento, "needs_pass", False):
            raise ErroreLettura("Il PDF è protetto da password: rimuovi la protezione e riprova.")
        totale = int(documento.page_count)
        quante = min(totale, limite) if limite else totale
        scala = dpi / 72.0
        for indice in range(quante):
            pagina = documento.load_page(indice)
            nativo = "" if solo_immagini else str(pagina.get_text("text") or "")
            if _testo_nativo_affidabile(nativo):
                esito = applica_formulario(nativo)
                pagine.append(PaginaTesto(indice + 1, esito.testo, ORIGINE_TESTO, 1.0, tabelle=_tabelle(pagina, indice + 1, nativo)))
                continue
            try:
                pixmap = pagina.get_pixmap(matrix=fitz.Matrix(scala, scala), alpha=False)
                immagine = Image.open(io.BytesIO(pixmap.tobytes("png"))).convert("RGB")
            except Exception as exc:
                pagine.append(PaginaTesto(indice + 1, "", ORIGINE_OCR, 0.0, (f"Pagina {indice + 1}: non convertita in immagine ({exc}).",)))
                continue
            try:
                letto = testo_da_immagine(immagine, pytesseract=pytesseract, lingua=lingua, raddrizza=False)
            except ErroreLettura as exc:
                pagine.append(PaginaTesto(indice + 1, "", ORIGINE_OCR, 0.0, (f"Pagina {indice + 1}: {exc}",)))
                continue
            finally:
                immagine.close()
            pagine.append(PaginaTesto(indice + 1, letto.testo, ORIGINE_OCR, letto.confidenza, letto.avvisi))
        if limite and totale > limite:
            pagine.append(PaginaTesto(quante + 1, "", ORIGINE_OCR, 0.0, (f"Lettura limitata a {limite} pagine su {totale}.",)))
    finally:
        documento.close()
    return pagine


__all__ = [
    "CARATTERI_TESTO_NATIVO_MINIMI",
    "DPI_RASTERIZZAZIONE",
    "ORIGINE_OCR",
    "ORIGINE_TESTO",
    "PaginaTesto",
    "TestoLetto",
    "testo_da_immagine",
    "testo_da_immagine_bytes",
    "testo_da_pdf",
]
