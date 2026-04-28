import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOKENS_PATH = ROOT / "tokens.json"
SCSS_TOKENS_PATH = ROOT / "web" / "static" / "scss" / "_design-tokens.scss"
APP_ICON_PATH = ROOT / "assets" / "icon" / "app.svg"


def _tokens() -> dict:
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def _hex_to_rgb(value: str) -> tuple[float, float, float]:
    raw = value.strip().lstrip("#")
    assert len(raw) == 6
    return tuple(int(raw[index : index + 2], 16) / 255 for index in (0, 2, 4))


def _linear(channel: float) -> float:
    if channel <= 0.03928:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    red, green, blue = (_linear(channel) for channel in _hex_to_rgb(hex_color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast(foreground: str, background: str) -> float:
    first = _luminance(foreground)
    second = _luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def test_tokens_file_contains_core_namespaces():
    tokens = _tokens()
    assert tokens["$schema"] == "https://design-tokens.org/schema.json"
    for namespace in ("color", "type", "size", "elevation", "motion", "icon"):
        assert namespace in tokens


def test_wcag_body_text_on_surface_is_accessible():
    tokens = _tokens()
    ratio = _contrast(tokens["color"]["text"]["primary"]["value"], tokens["color"]["surface"]["value"])
    assert ratio >= 4.5


def test_touch_target_minimum_is_44_px():
    tokens = _tokens()
    assert int(tokens["size"]["touch"]["min"]["value"].replace("px", "")) >= 44


def test_elevation_and_motion_tokens_are_valid():
    tokens = _tokens()
    for level in ("level1", "level2", "level3", "level4"):
        assert "rgba(" in tokens["elevation"][level]["value"]
    for duration in tokens["motion"]["duration"].values():
        assert str(duration["value"]).endswith("ms")


def test_css_custom_properties_export_core_tokens():
    css = SCSS_TOKENS_PATH.read_text(encoding="utf-8")
    expected_vars = (
        "--color-brand-primary",
        "--color-brand-primary-variant",
        "--color-accent",
        "--color-text-primary",
        "--size-touch-min",
        "--motion-duration-short",
        "--elevation-level2",
    )
    for var_name in expected_vars:
        assert var_name in css
    assert "prefers-reduced-motion" in css


def test_store_icon_svg_is_clean_and_scalable():
    svg = APP_ICON_PATH.read_text(encoding="utf-8")
    root = ET.fromstring(svg)
    assert root.attrib.get("viewBox") == "0 0 1024 1024"
    assert "transform=" not in svg
    paths = re.findall(r"<path\b", svg)
    assert len(paths) <= 6
