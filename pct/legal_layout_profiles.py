"""Profili layout per atti generati da template.

Il modulo mantiene il contratto di impaginazione separato dal compilatore:
ogni template deve risolversi in un profilo layout e in una politica timbro
prima di poter diventare bozza finale o documento esportabile.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Callable


RULES_DIR = Path(__file__).with_name("legal_rules")
LAYOUT_RULES_FILE = RULES_DIR / "redaction_layout_rules.yml"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _load_json_yaml(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


@dataclass(slots=True)
class StudioStampPlacement:
    position: str = "top_left"
    repeat_on_each_page: bool = True
    align_within_box: str = "center"
    line_align: str = "left"
    margin_top_mm: int = 18
    margin_left_mm: int = 18
    box_width_mm: int = 82
    box_height_mm: int = 22
    bottom_gap_mm: int = 10
    avoid_overlap: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ActLayoutProfile:
    id: str
    title: str
    page_format: str = "A4"
    margin_top_mm: int = 42
    margin_right_mm: int = 22
    margin_bottom_mm: int = 25
    margin_left_mm: int = 32
    font_family: str = "Times New Roman"
    font_size_pt: int = 12
    line_height: float = 1.75
    text_align: str = "justify"
    requires_stamp: bool = True
    stamp_position: str = "top_left"
    stamp_repeat: str = "each_page"
    reason: str = ""
    stamp: StudioStampPlacement = field(default_factory=StudioStampPlacement)

    @property
    def stamp_policy_ok(self) -> bool:
        return (
            self.stamp_position == "top_left"
            and self.stamp_repeat == "each_page"
            and self.stamp.position == "top_left"
            and self.stamp.repeat_on_each_page
        )

    def to_editor_layout(self) -> dict[str, Any]:
        return {
            "font_family": self.font_family,
            "font_size_pt": self.font_size_pt,
            "line_height": self.line_height,
            "text_align": self.text_align,
            "margin_top_mm": self.margin_top_mm,
            "margin_right_mm": self.margin_right_mm,
            "margin_bottom_mm": self.margin_bottom_mm,
            "margin_left_mm": self.margin_left_mm,
            "paragraph_spacing_pt": 8,
        }

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stamp_policy_ok"] = self.stamp_policy_ok
        return payload


def _layout_from_row(row: dict[str, Any]) -> ActLayoutProfile:
    stamp = StudioStampPlacement(
        position=_clean(row.get("stamp_position")) or "top_left",
        repeat_on_each_page=_clean(row.get("stamp_repeat")) in {"each_page", "all_pages", "tutte_le_pagine", ""},
        align_within_box="center",
        line_align="left",
    )
    return ActLayoutProfile(
        id=_clean(row.get("id")) or "generic_internal_draft_layout",
        title=_clean(row.get("title")) or _clean(row.get("id")) or "Layout atto",
        page_format=_clean(row.get("page_format")) or "A4",
        margin_top_mm=int(row.get("margin_top_mm") or 42),
        margin_right_mm=int(row.get("margin_right_mm") or 22),
        margin_bottom_mm=int(row.get("margin_bottom_mm") or 25),
        margin_left_mm=int(row.get("margin_left_mm") or 32),
        font_family=_clean(row.get("font_family")) or "Times New Roman",
        font_size_pt=int(row.get("font_size_pt") or 12),
        line_height=float(row.get("line_height") or 1.75),
        text_align=_clean(row.get("text_align")) or "justify",
        requires_stamp=bool(row.get("requires_stamp", True)),
        stamp_position=_clean(row.get("stamp_position")) or "top_left",
        stamp_repeat=_clean(row.get("stamp_repeat")) or "each_page",
        reason=_clean(row.get("reason")),
        stamp=stamp,
    )


def load_layout_profiles() -> dict[str, ActLayoutProfile]:
    payload = _load_json_yaml(LAYOUT_RULES_FILE)
    profiles: dict[str, ActLayoutProfile] = {}
    for row in payload.get("layout_profiles") or []:
        if not isinstance(row, dict):
            continue
        profile = _layout_from_row(row)
        profiles[profile.id] = profile
    return profiles


def get_layout_profile(profile_id: str | None) -> ActLayoutProfile | None:
    profiles = load_layout_profiles()
    if profile_id and profile_id in profiles:
        return profiles[profile_id]
    return profiles.get("generic_internal_draft_layout")


def css_for_stamp_repeated(stamp: Any, layout_profile: ActLayoutProfile | None = None) -> str:
    if not stamp or not getattr(stamp, "enabled", False):
        return ""
    placement = getattr(stamp, "to_stamp_placement", lambda: StudioStampPlacement().to_dict())()
    top = int(placement.get("margin_top_mm") or 18)
    left = int(placement.get("margin_left_mm") or 18)
    width = int(placement.get("box_width_mm") or 82)
    return (
        "@page { @top-left { content: element(iusentra-studio-timbro); } }\n"
        ".iusentra-studio-timbro{"
        "position:running(iusentra-studio-timbro);"
        f"width:{width}mm;margin:{top}mm 0 0 {left}mm;"
        "text-align:left;}"
    )


def _stamp_position_key(value: Any) -> str:
    raw = _clean(value).lower().replace("_", "-")
    if raw in {"top-left", "top-center", "top-right", "middle-left", "middle-right"}:
        return raw
    if raw == "top_left":
        return "top-left"
    return "top-left"


def make_pdf_stamp_callback(
    stamp: Any,
    layout_profile: ActLayoutProfile | None = None,
    layout: dict[str, Any] | None = None,
) -> Callable[[Any, Any], None] | None:
    if not stamp or not getattr(stamp, "enabled", False):
        return None
    placement = getattr(stamp, "to_stamp_placement", lambda: StudioStampPlacement().to_dict())()
    layout_cfg = layout or {}
    position = _stamp_position_key(layout_cfg.get("stamp_position") or (layout_profile.stamp_position if layout_profile else None))
    try:
        vertical_offset_mm = float(layout_cfg.get("stamp_offset_y_mm") or 0)
    except (TypeError, ValueError):
        vertical_offset_mm = 0.0

    def _draw(canvas: Any, _doc: Any) -> None:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
        except Exception:
            return
        lines = list(getattr(stamp, "to_lines", lambda: [])() or [])
        if not lines:
            return
        page_width, page_height = A4
        width = float(placement.get("box_width_mm") or 82) * mm
        margin_left = float(placement.get("margin_left_mm") or 18) * mm
        margin_top = float(placement.get("margin_top_mm") or 18)
        top_mm = margin_top + vertical_offset_mm
        if position.startswith("middle-"):
            top_mm = 128 + vertical_offset_mm
        if position.endswith("center"):
            left = max(0, (page_width - width) / 2)
        elif position.endswith("right"):
            left = page_width - margin_left - width
        else:
            left = margin_left
        y = page_height - (top_mm * mm)
        canvas.saveState()
        for line in lines:
            size = int(line.get("size") or 9)
            font = "Helvetica-Bold" if line.get("bold") else "Helvetica"
            canvas.setFont(font, size)
            text = _clean(line.get("text"))
            if placement.get("align_within_box", "center") == "center":
                text_width = canvas.stringWidth(text, font, size)
                x = left + max(0, (width - text_width) / 2)
            else:
                x = left
            canvas.drawString(x, y, text)
            y -= max(size + 1, size * 1.22)
        canvas.restoreState()

    return _draw


def top_margin_with_stamp(layout_cfg: dict[str, Any], stamp: Any) -> float:
    base = float(layout_cfg.get("margin_top_mm") or 25)
    if not stamp or not getattr(stamp, "enabled", False):
        return base
    placement = getattr(stamp, "to_stamp_placement", lambda: StudioStampPlacement().to_dict())()
    required = (
        float(placement.get("margin_top_mm") or 18)
        + float(placement.get("box_height_mm") or 22)
        + float(placement.get("bottom_gap_mm") or 10)
    )
    return max(base, required)
