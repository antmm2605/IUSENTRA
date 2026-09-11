"""Riconoscimento del testo (OCR) di una pagina acquisita da scanner o fotocamera.

La pagina viene elaborata in memoria e restituita come PDF con testo ricercabile
insieme ai paragrafi riconosciuti. Nessun contenuto viene persistito: il
salvataggio nel fascicolo resta un'azione esplicita dell'avvocato.

Base normativa: la copia informatica per immagine di documento analogico
(D.Lgs. 82/2005, art. 22) resta una scansione; l'OCR aggiunge solo lo strato di
testo selezionabile e non trasforma la scansione in atto nativo digitale
(Specifiche tecniche DGSIA D.M. 44/2011, art. 15, comma 1, lett. c).
"""

from __future__ import annotations

import io
import os
import re
import threading
from dataclasses import dataclass

from web.services.document_tools import DocumentToolError


MAX_OCR_IMAGE_BYTES = 60 * 1024 * 1024
MAX_OCR_PIXELS = 50_000_000
OCR_LANGUAGE = "ita"
OCR_TIMEOUT_SECONDS = 120
A4_WIDTH_INCHES = 210 / 25.4
A4_HEIGHT_INCHES = 297 / 25.4

_OCR_SLOTS = threading.BoundedSemaphore(max(1, int(os.environ.get("IUSENTRA_OCR_PAGE_CONCURRENCY", "2") or 2)))


@dataclass(frozen=True)
class OcrPageResult:
    pdf: bytes
    paragraphs: list[str]
    dpi: int

    @property
    def characters(self) -> int:
        return sum(len(re.sub(r"\s+", "", paragraph)) for paragraph in self.paragraphs)


def page_dpi(width: int, height: int) -> int:
    """Risoluzione che fa rientrare la pagina nel formato A4 (orientamento dell'immagine)."""
    long_side, short_side = max(width, height), min(width, height)
    dpi = max(long_side / A4_HEIGHT_INCHES, short_side / A4_WIDTH_INCHES)
    return int(min(600, max(72, round(dpi))))


def _load_page(data: bytes, rotation: int):
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    if not data:
        raise DocumentToolError("La pagina da riconoscere è vuota.")
    if len(data) > MAX_OCR_IMAGE_BYTES:
        raise DocumentToolError("La pagina supera 60 MB.")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in {"JPEG", "PNG", "WEBP"}:
            raise DocumentToolError("Usa una pagina JPEG, PNG o WebP.")
        if image.width * image.height > MAX_OCR_PIXELS:
            raise DocumentToolError("La pagina supera 50 megapixel.")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except DocumentToolError:
        raise
    except Exception as exc:
        raise DocumentToolError("La pagina non è un'immagine leggibile.") from exc
    angle = int(rotation or 0) % 360
    if angle in {90, 180, 270}:
        # Rotazione in senso orario, come l'anteprima dell'avvocato e il PDF multipagina.
        image = image.rotate(-angle, expand=True)
    return image


def _join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        if text.endswith("-") and line[:1].islower():
            text = text[:-1] + line
        else:
            text = f"{text} {line}".strip()
    return re.sub(r"\s+", " ", text).strip()


def paragraphs_from_pdf(pdf: bytes) -> list[str]:
    """Paragrafi dal livello di testo del PDF prodotto dall'OCR.

    Le righe vicine e allineate a sinistra vengono unite nello stesso paragrafo; una
    riga vuota o un rientro diverso aprono un nuovo paragrafo. La sillabazione a fine
    riga viene ricomposta.
    """
    import fitz  # type: ignore

    paragraphs: list[str] = []
    with fitz.open(stream=pdf, filetype="pdf") as document:
        for page in document:
            current: list[str] = []
            previous: tuple[float, float, float] | None = None  # x0, y1, altezza riga
            for block in page.get_text("blocks", sort=True):
                if len(block) < 5 or (len(block) > 6 and block[6] != 0):
                    continue
                lines = [line.strip() for line in str(block[4] or "").splitlines() if line.strip()]
                if not lines:
                    continue
                x0, y0, y1 = float(block[0]), float(block[1]), float(block[3])
                line_height = max(1.0, (y1 - y0) / len(lines))
                continues = previous is not None and (y0 - previous[1]) < 0.8 * max(line_height, previous[2]) and abs(x0 - previous[0]) < 2.5 * line_height
                if current and not continues:
                    paragraphs.append(_join_lines(current))
                    current = []
                current.extend(lines)
                previous = (x0, y1, line_height)
            if current:
                paragraphs.append(_join_lines(current))
    return [paragraph for paragraph in paragraphs if paragraph]


_LANGUAGE_READY = False


def _tesseract():
    global _LANGUAGE_READY
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - dipendenza del runtime Docker
        raise DocumentToolError("Il riconoscimento del testo non è disponibile su questa installazione.") from exc
    if _LANGUAGE_READY:
        return pytesseract
    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        raise DocumentToolError("Il motore di riconoscimento del testo non è installato sul server.") from exc
    if OCR_LANGUAGE not in languages:
        raise DocumentToolError("Il dizionario italiano per il riconoscimento del testo non è installato sul server.")
    _LANGUAGE_READY = True
    return pytesseract


def recognize_page(data: bytes, rotation: int = 0) -> OcrPageResult:
    """OCR in lingua italiana di una pagina; restituisce PDF ricercabile e paragrafi."""
    pytesseract = _tesseract()
    image = _load_page(data, rotation)
    dpi = page_dpi(image.width, image.height)
    if not _OCR_SLOTS.acquire(timeout=45):
        raise DocumentToolError("Il riconoscimento del testo è impegnato da altre pagine. Riprova tra qualche istante.")
    try:
        pdf = pytesseract.image_to_pdf_or_hocr(
            image,
            lang=OCR_LANGUAGE,
            extension="pdf",
            config=f"--dpi {dpi}",
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except RuntimeError as exc:
        raise DocumentToolError("Il riconoscimento della pagina ha richiesto troppo tempo. Migliora luce e nitidezza e riprova.") from exc
    except Exception as exc:
        raise DocumentToolError("Riconoscimento del testo non completato per questa pagina.") from exc
    finally:
        _OCR_SLOTS.release()
        image.close()
    if not pdf or not bytes(pdf).startswith(b"%PDF-"):
        raise DocumentToolError("Riconoscimento del testo non completato per questa pagina.")
    return OcrPageResult(pdf=bytes(pdf), paragraphs=paragraphs_from_pdf(bytes(pdf)), dpi=dpi)
