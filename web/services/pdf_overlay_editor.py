"""Editor PDF nativo a overlay per il fascicolo.

Il modulo non converte mai il PDF in HTML: apre il PDF originale, applica
interventi grafici espliciti sulle pagine e restituisce un nuovo PDF.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

import fitz


class PdfOverlayError(ValueError):
    """Annotazione PDF non valida o PDF non modificabile."""


@dataclass(frozen=True)
class PdfPageInfo:
    number: int
    width: float
    height: float


def pdf_page_infos(pdf_bytes: bytes) -> list[PdfPageInfo]:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [
            PdfPageInfo(number=index + 1, width=float(page.rect.width), height=float(page.rect.height))
            for index, page in enumerate(doc)
        ]


def render_pdf_page_png(pdf_bytes: bytes, *, page_number: int, zoom: float = 1.6) -> bytes:
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if page_number < 1 or page_number > len(doc):
            raise PdfOverlayError("Pagina PDF non disponibile.")
        page = doc[page_number - 1]
        matrix = fitz.Matrix(max(0.5, min(float(zoom or 1.6), 3.0)), max(0.5, min(float(zoom or 1.6), 3.0)))
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        return bytes(pixmap.tobytes("png"))


def apply_pdf_overlays(pdf_bytes: bytes, annotations: Iterable[dict[str, Any]]) -> tuple[bytes, int]:
    normalized = [_normalize_annotation(item) for item in annotations]
    if not normalized:
        raise PdfOverlayError("Nessuna modifica PDF da salvare.")
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.is_encrypted:
            raise PdfOverlayError("PDF cifrato: importare una versione sbloccata prima della modifica.")
        for annotation in normalized:
            page_number = int(annotation["page"])
            if page_number < 1 or page_number > len(doc):
                raise PdfOverlayError("Una modifica indica una pagina PDF non disponibile.")
            _apply_annotation(doc[page_number - 1], annotation)
        return bytes(doc.tobytes(garbage=4, deflate=True, clean=True)), len(normalized)


def _normalize_annotation(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PdfOverlayError("Annotazione PDF non valida.")
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in {"text", "highlight", "cover"}:
        raise PdfOverlayError("Tipo modifica PDF non supportato.")
    page = _int(raw.get("page"), "Pagina PDF non valida.")
    x = _ratio(raw.get("x"), "Coordinata X non valida.")
    y = _ratio(raw.get("y"), "Coordinata Y non valida.")
    annotation: dict[str, Any] = {
        "type": kind,
        "page": page,
        "x": x,
        "y": y,
        "color": _color(raw.get("color"), "#111827"),
        "fillColor": _color(raw.get("fillColor"), "#fef3c7"),
    }
    if kind == "text":
        text = str(raw.get("text") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            raise PdfOverlayError("Il testo da applicare al PDF è vuoto.")
        if len(text) > 1200:
            raise PdfOverlayError("Il testo della modifica PDF è troppo lungo.")
        annotation["text"] = text
        annotation["fontSizePt"] = min(max(_float(raw.get("fontSizePt"), 12.0), 6.0), 48.0)
    else:
        annotation["width"] = min(max(_float(raw.get("width"), 0.2), 0.01), 1.0)
        annotation["height"] = min(max(_float(raw.get("height"), 0.04), 0.01), 1.0)
    return annotation


def _apply_annotation(page: fitz.Page, annotation: dict[str, Any]) -> None:
    width = float(page.rect.width)
    height = float(page.rect.height)
    x = width * float(annotation["x"])
    y = height * float(annotation["y"])
    kind = str(annotation["type"])
    if kind == "text":
        page.insert_text(
            fitz.Point(x, y),
            str(annotation["text"]),
            fontsize=float(annotation["fontSizePt"]),
            fontname="helv",
            color=_rgb(annotation["color"]),
            overlay=True,
        )
        return

    rect = fitz.Rect(
        x,
        y,
        min(width, x + width * float(annotation["width"])),
        min(height, y + height * float(annotation["height"])),
    )
    if kind == "cover":
        page.draw_rect(rect, color=(0.82, 0.86, 0.91), fill=(1.0, 1.0, 1.0), width=0.6, overlay=True)
        return
    page.draw_rect(rect, color=None, fill=_rgb(annotation["fillColor"]), fill_opacity=0.35, overlay=True)


def _int(value: Any, message: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise PdfOverlayError(message) from None
    if parsed < 1:
        raise PdfOverlayError(message)
    return parsed


def _float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _ratio(value: Any, message: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise PdfOverlayError(message) from None
    if parsed < 0 or parsed > 1:
        raise PdfOverlayError(message)
    return parsed


def _color(value: Any, default: str) -> str:
    raw = str(value or default).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        return default
    return raw.lower()


def _rgb(value: str) -> tuple[float, float, float]:
    hex_value = _color(value, "#111827").lstrip("#")
    return (
        int(hex_value[0:2], 16) / 255.0,
        int(hex_value[2:4], 16) / 255.0,
        int(hex_value[4:6], 16) / 255.0,
    )
