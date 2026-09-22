"""Editor PDF nativo a overlay per il fascicolo.

Il modulo non converte mai il PDF in HTML: apre il PDF originale, applica
interventi grafici espliciti sulle pagine e restituisce un nuovo PDF.

Due regole governano il salvataggio, e sono in tensione fra loro.

La prima: un documento che puo' finire agli atti va modificato *aggiungendo*,
non riscrivendo. Il salvataggio incrementale lascia intatti i byte originali e
accoda le modifiche, cosi' dentro il file modificato l'originale resta
verificabile.

La seconda: un oscuramento deve togliere davvero il testo. Finche' si disegnava
un rettangolo bianco sopra, il testo restava nel contenuto della pagina e si
riprendeva con un copia-incolla: sembrava coperto e non lo era.

Le due cose non convivono. Un salvataggio incrementale conserva la revisione
precedente, quindi conserverebbe anche il testo che l'oscuramento doveva
distruggere. Percio': se fra le modifiche c'e' un oscuramento il file viene
riscritto per intero, e solo in quel caso.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
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
    """Misure delle pagine. Sola lettura: passa dal motore di rendering."""
    from pct.rendering_pdf import RenderingPdfError, dimensioni_pagine

    try:
        return [
            PdfPageInfo(number=misura.numero, width=misura.larghezza, height=misura.altezza)
            for misura in dimensioni_pagine(pdf_bytes)
        ]
    except RenderingPdfError as exc:
        raise PdfOverlayError(str(exc)) from exc


def render_pdf_page_png(pdf_bytes: bytes, *, page_number: int, zoom: float = 1.6) -> bytes:
    """Una pagina come immagine. Sola lettura: passa dal motore di rendering."""
    from pct.rendering_pdf import RenderingPdfError, pagina_png

    try:
        return pagina_png(pdf_bytes, numero_pagina=page_number, scala=zoom, predefinita=1.6)
    except RenderingPdfError as exc:
        raise PdfOverlayError(str(exc)) from exc


def apply_pdf_overlays(pdf_bytes: bytes, annotations: Iterable[dict[str, Any]]) -> tuple[bytes, int]:
    """Applica le modifiche e restituisce il PDF nuovo con quante ne ha applicate.

    Senza oscuramenti il file esce da un salvataggio incrementale: i byte
    dell'originale restano dov'erano. Con almeno un oscuramento il file viene
    riscritto, perche' il testo tolto non deve sopravvivere in una revisione
    precedente.
    """
    normalized = [_normalize_annotation(item) for item in annotations]
    if not normalized:
        raise PdfOverlayError("Nessuna modifica PDF da salvare.")
    oscura = any(str(item.get("type")) == "cover" for item in normalized)
    with tempfile.TemporaryDirectory(prefix="iusentra-pdf-") as cartella:
        lavoro = Path(cartella) / "documento.pdf"
        lavoro.write_bytes(pdf_bytes)
        with fitz.open(str(lavoro)) as doc:
            if doc.is_encrypted:
                raise PdfOverlayError("PDF cifrato: importare una versione sbloccata prima della modifica.")
            pagine_da_oscurare: set[int] = set()
            for annotation in normalized:
                page_number = int(annotation["page"])
                if page_number < 1 or page_number > len(doc):
                    raise PdfOverlayError("Una modifica indica una pagina PDF non disponibile.")
                _apply_annotation(doc[page_number - 1], annotation)
                if str(annotation["type"]) == "cover":
                    pagine_da_oscurare.add(page_number - 1)
            for indice in sorted(pagine_da_oscurare):
                _esegui_oscuramenti(doc[indice])
            if oscura:
                # Riscrittura piena: la revisione precedente conteneva il testo
                # oscurato e non deve restare nel file.
                return bytes(doc.tobytes(garbage=4, deflate=True, clean=True)), len(normalized)
            doc.save(str(lavoro), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        return lavoro.read_bytes(), len(normalized)


def _esegui_oscuramenti(page: fitz.Page) -> None:
    """Toglie davvero il contenuto sotto i rettangoli di oscuramento."""
    try:
        page.apply_redactions()
    except TypeError:
        # Versioni piu' vecchie non accettano argomenti opzionali.
        page.apply_redactions()


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
        # Oscuramento vero: si marca l'area e il contenuto sotto viene tolto
        # dalla pagina quando si applicano le redazioni. Un rettangolo disegnato
        # sopra lascerebbe il testo nel file, recuperabile con un copia-incolla.
        page.add_redact_annot(rect, fill=(1.0, 1.0, 1.0))
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
