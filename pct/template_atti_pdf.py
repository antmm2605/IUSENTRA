"""Timbro dello studio nei PDF generati dall'editor atti.

Quando il layout arriva dall'editor (``stamp_anchor = page_margin``) il timbro
va disegnato esattamente dove l'editor lo mostra: dal margine superiore della
pagina, con font, corpo e interlinea scelti, allineato come nell'intestazione
dei fogli; il testo del corpo parte subito sotto (vedi ``PageSetup.body_top_mm``).
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

from pct.template_atti_page_setup import PageSetup

_PDF_FONTS = {
    "times": ("Times-Roman", "Times-Bold"),
    "helvetica": ("Helvetica", "Helvetica-Bold"),
    "courier": ("Courier", "Courier-Bold"),
}


def _stamp_fonts(setup: PageSetup) -> tuple[str, str]:
    try:
        from pct.template_atti import font_editor

        family = str(font_editor(setup.stamp_font_family).get("pdf_family") or "courier").lower()
    except Exception:
        family = "courier"
    return _PDF_FONTS.get(family, _PDF_FONTS["courier"])


def make_editor_stamp_callback(stamp_lines: Sequence[Mapping[str, Any]], setup: PageSetup) -> Callable[[Any, Any], None] | None:
    lines = [line for line in stamp_lines if str(line.get("text") or "").strip()]
    if not lines:
        return None
    regular, bold = _stamp_fonts(setup)
    size = float(setup.stamp_font_size_pt)
    leading = size * float(setup.stamp_line_height)

    def _draw(canvas: Any, _doc: Any) -> None:
        from reportlab.lib.units import mm

        page_width, page_height = canvas._pagesize
        widths = [canvas.stringWidth(str(line.get("text") or "").strip(), bold if line.get("bold") else regular, size) for line in lines]
        box_width = max(widths) if widths else 0
        if setup.stamp_alignment == "left":
            box_left = setup.margin_left_mm * mm
        elif setup.stamp_alignment == "right":
            box_left = page_width - (setup.margin_right_mm * mm) - box_width
        else:
            box_left = (page_width - box_width) / 2
        baseline = page_height - (setup.stamp_top_mm() * mm) - (leading - size) / 2 - size * 0.8
        canvas.saveState()
        for line, width in zip(lines, widths):
            font = bold if line.get("bold") else regular
            canvas.setFont(font, size)
            canvas.drawString(box_left + max(0, (box_width - width) / 2), baseline, str(line.get("text") or "").strip())
            baseline -= leading
        canvas.restoreState()

    return _draw
