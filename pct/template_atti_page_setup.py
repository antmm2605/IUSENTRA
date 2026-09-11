"""Impostazione pagina condivisa tra editor atti ed esportazioni.

L'editor degli atti (``/template-atti/editor``) mostra fogli A4 reali: margini,
orientamento, timbro dello studio ripetuto in intestazione e interruzioni di
pagina. RTF, DOCX e PDF devono riprodurre la stessa geometria, così il documento
esportato coincide con quello visto durante la redazione.

Base normativa: il formato dell'atto resta quello richiesto per il deposito
telematico (PDF testuale, D.M. 44/2011 art. 12 e Specifiche tecniche DGSIA);
questo modulo non introduce regole di contenuto, solo la fedeltà di impaginazione.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

A4_WIDTH_MM = 210.0
A4_HEIGHT_MM = 297.0
MM_PER_PT = 25.4 / 72.0
TWIPS_PER_MM = 1440.0 / 25.4
STAMP_TEXT_GAP_MM = 6.0
MIDDLE_STAMP_TOP_MM = 128.0
MINIMUM_BODY_HEIGHT_MM = 40.0
PAGE_BREAK_ATTRIBUTE = "data-iu-page-break"


@dataclass(frozen=True)
class PageSetup:
    orientation: str
    width_mm: float
    height_mm: float
    margin_top_mm: float
    margin_right_mm: float
    margin_bottom_mm: float
    margin_left_mm: float
    stamp_position: str
    stamp_offset_y_mm: float
    stamp_font_family: str
    stamp_font_size_pt: float
    stamp_line_height: float

    @property
    def landscape(self) -> bool:
        return self.orientation == "orizzontale"

    @property
    def stamp_at_top(self) -> bool:
        return self.stamp_position.startswith("top-")

    @property
    def stamp_alignment(self) -> str:
        if self.stamp_position.endswith("left"):
            return "left"
        if self.stamp_position.endswith("right"):
            return "right"
        return "center"

    def stamp_top_mm(self) -> float:
        base = self.margin_top_mm if self.stamp_at_top else MIDDLE_STAMP_TOP_MM
        return max(0.0, base + self.stamp_offset_y_mm)

    def stamp_height_mm(self, line_count: int) -> float:
        if line_count <= 0:
            return 0.0
        return line_count * self.stamp_font_size_pt * self.stamp_line_height * MM_PER_PT

    def body_top_mm(self, stamp_line_count: int) -> float:
        """Inizio del testo su ogni pagina: sotto il timbro, come nell'editor."""
        if stamp_line_count <= 0 or not self.stamp_at_top:
            return self.margin_top_mm
        reserve = max(0.0, self.stamp_height_mm(stamp_line_count) + self.stamp_offset_y_mm)
        requested = self.margin_top_mm + reserve + STAMP_TEXT_GAP_MM
        ceiling = self.height_mm - self.margin_bottom_mm - MINIMUM_BODY_HEIGHT_MM
        return max(self.margin_top_mm, min(requested, ceiling))


def page_setup_from_layout(layout: Mapping[str, Any] | None) -> PageSetup:
    from pct.template_atti import normalizza_editor_layout

    cfg = normalizza_editor_layout(dict(layout or {}))
    landscape = cfg["page_orientation"] == "orizzontale"
    return PageSetup(
        orientation=cfg["page_orientation"],
        width_mm=A4_HEIGHT_MM if landscape else A4_WIDTH_MM,
        height_mm=A4_WIDTH_MM if landscape else A4_HEIGHT_MM,
        margin_top_mm=float(cfg["margin_top_mm"]),
        margin_right_mm=float(cfg["margin_right_mm"]),
        margin_bottom_mm=float(cfg["margin_bottom_mm"]),
        margin_left_mm=float(cfg["margin_left_mm"]),
        stamp_position=str(cfg["stamp_position"]),
        stamp_offset_y_mm=float(cfg["stamp_offset_y_mm"]),
        stamp_font_family=str(cfg["stamp_font_family"]),
        stamp_font_size_pt=float(cfg["stamp_font_size_pt"]),
        stamp_line_height=float(cfg["stamp_line_height"]),
    )


def mm_to_twips(value_mm: float) -> int:
    return int(round(float(value_mm) * TWIPS_PER_MM))


def stamp_lines_from_timbro(timbro: Any) -> list[dict[str, Any]]:
    """Righe del timbro studio (testo e grassetto), vuote se il timbro non è attivo."""
    if not timbro or not getattr(timbro, "enabled", False):
        return []
    try:
        lines: Iterable[Any] = timbro.to_lines() or []
    except Exception:
        lines = []
    result: list[dict[str, Any]] = []
    for line in lines:
        text = str(line.get("text") if isinstance(line, Mapping) else getattr(line, "text", "")).strip()
        if not text:
            continue
        bold = bool(line.get("bold")) if isinstance(line, Mapping) else bool(getattr(line, "bold", False))
        result.append({"text": text, "bold": bold})
    if not result:
        raw = str(getattr(timbro, "text", "") or "")
        result = [{"text": item.strip(), "bold": False} for item in raw.splitlines() if item.strip()]
    return result


def is_page_break_element(tag: str, attrs: Mapping[str, Any] | Iterable[tuple[str, Any]]) -> bool:
    if str(tag or "").lower() != "hr":
        return False
    items = attrs.items() if isinstance(attrs, Mapping) else attrs
    for name, value in items:
        key = str(name or "").lower()
        if key == PAGE_BREAK_ATTRIBUTE:
            return True
        if key == "class" and "iu-ted-page-break" in str(value or "").split():
            return True
    return False
