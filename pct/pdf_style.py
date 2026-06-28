"""Stili PDF condivisi da IUSENTRA."""

from __future__ import annotations

from typing import Any

from reportlab.lib import colors


PDF_TABLE_HEADER_BACKGROUND = colors.white
PDF_TABLE_HEADER_TEXT = colors.HexColor("#111827")
PDF_TABLE_HEADER_ACCENT = colors.HexColor("#1a3a5c")


def pdf_table_header_style(
    *,
    start: tuple[int, int] = (0, 0),
    end: tuple[int, int] = (-1, 0),
    font_name: str = "Helvetica-Bold",
    line_width: float = 0.8,
) -> list[tuple[Any, ...]]:
    """Regola unica per le intestazioni delle tabelle nei PDF IUSENTRA."""

    return [
        ("BACKGROUND", start, end, PDF_TABLE_HEADER_BACKGROUND),
        ("TEXTCOLOR", start, end, PDF_TABLE_HEADER_TEXT),
        ("FONTNAME", start, end, font_name),
        ("LINEBELOW", start, end, line_width, PDF_TABLE_HEADER_ACCENT),
    ]
