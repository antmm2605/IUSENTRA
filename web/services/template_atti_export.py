"""Orchestrazione degli export RTF e DOCX dell'editor atti.

Traduce il layout dell'editor (font, corpo, interlinea, allineamento, pagina e
timbro) nei writer di dominio ``pct.template_atti_rtf`` e ``pct.template_atti_docx``.
"""

from __future__ import annotations

import io
from typing import Any, Mapping

from pct.template_atti_page_setup import page_setup_from_layout, stamp_lines_from_timbro


def _font_meta(key: str) -> dict[str, Any]:
    try:
        from pct.template_atti import font_editor

        return dict(font_editor(str(key or "")) or {})
    except Exception:
        return {}


def _float_between(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        return max(minimum, min(maximum, float(value)))
    except (TypeError, ValueError):
        return default


def export_typography(layout: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(layout or {})
    body_meta = _font_meta(str(raw.get("font_family") or ""))
    stamp_meta = _font_meta(str(raw.get("stamp_font_family") or raw.get("placeholder_font_family") or ""))
    align = str(raw.get("text_align") or raw.get("textAlign") or "justify").lower()
    return {
        "font_size": _float_between(raw.get("font_size_pt") or raw.get("font_size") or raw.get("fontSize"), 12.0, 4.0, 28.0),
        "line_height": _float_between(raw.get("line_height") or raw.get("lineHeight"), 1.45, 1.0, 2.6),
        "text_align": align if align in {"left", "center", "right", "justify"} else "justify",
        "docx_font": str(body_meta.get("docx_family") or raw.get("fallback_font_family") or "Times New Roman"),
        "rtf_font": str(body_meta.get("rtf_family") or "Times New Roman"),
        "stamp_docx_font": str(stamp_meta.get("docx_family") or "Courier New"),
        "stamp_rtf_font": str(stamp_meta.get("rtf_family") or "Courier New"),
    }


def build_rtf_export(testo: str, layout: Mapping[str, Any] | None, *, timbro: Any = None, html_content: str | None = None) -> str:
    from pct.template_atti_rtf import build_rtf_document

    typography = export_typography(layout)
    return build_rtf_document(
        setup=page_setup_from_layout(layout),
        body_font=typography["rtf_font"],
        stamp_font=typography["stamp_rtf_font"],
        font_size_pt=typography["font_size"],
        line_height=typography["line_height"],
        text_align=typography["text_align"],
        stamp_lines=stamp_lines_from_timbro(timbro),
        html=html_content or "",
        text=testo or "",
    )


def build_docx_export(testo: str, layout: Mapping[str, Any] | None, *, timbro: Any = None, html_content: str | None = None) -> io.BytesIO:
    from docx import Document

    from pct.template_atti_docx import append_html, append_text, apply_page_setup, write_stamp_header

    typography = export_typography(layout)
    setup = page_setup_from_layout(layout)
    stamp_lines = stamp_lines_from_timbro(timbro)
    document = Document()
    apply_page_setup(document, setup, stamp_line_count=len(stamp_lines))
    write_stamp_header(document, setup, stamp_lines, font_name=typography["stamp_docx_font"])
    options = {
        "font_name": typography["docx_font"],
        "font_size": typography["font_size"],
        "line_height": typography["line_height"],
        "default_align": typography["text_align"],
    }
    if html_content:
        append_html(document, html_content, **options)
    else:
        append_text(document, testo or "", **options)
    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)
    return buffer
