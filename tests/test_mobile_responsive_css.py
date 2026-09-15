from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def _css(name: str) -> str:
    return (ROOT / "frontend" / "src" / "components" / name).read_text(
        encoding="utf-8"
    )


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_fascicoli_mobile_stats_are_not_horizontal_carousel() -> None:
    css = _css("FascicoliPage.css")
    mobile_block = re.search(r"@media\(max-width:760px\)\{(?P<body>.*?)\.iu-fas-toolbar", css, re.S)
    assert mobile_block is not None
    body = mobile_block.group("body")
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in body
    assert "overflow:visible" in body
    assert "scroll-snap-type:none" in body
    assert ".iu-fas-stats{display:flex;grid-template-columns:none" not in css
    assert "min-width:0;min-height:66px" in body


def test_email_mobile_header_and_stats_remain_compact() -> None:
    css = _css("EmailPecPage.css")
    assert ".iu-mail-hero p{display:none}" in css
    assert ".iu-mail-hero__actions{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert ".iusentra-preset-active .iu-email-page .iu-mail-stats" in css
    assert ".iu-mail-stat{min-height:70px;grid-template-columns:30px minmax(0,1fr)" in css


def test_mobile_sidebar_overlays_topbar_and_hides_bottom_nav() -> None:
    app = re.sub(r"\s+", "", _read("frontend/src/App.tsx"))
    css = _read("frontend/src/index.css")
    assert "iu-shell--mobile-menu-open" in app
    assert "!embeddedViewer&&!mobileMenuOpen?<nav" in app
    assert "body.react-shell-page.iu-mobile-menu-open{overflow:hidden!important}" in css
    assert re.search(
        r"\.iu-shell\.iu-shell--mobile-menu-open\s+\.iu-sidebar\.iu-sidebar--mobile-open\s*\{[^}]*z-index:430",
        css,
        re.S,
    )
    assert re.search(
        r"\.iu-shell\.iu-shell--mobile-menu-open\s+\.iu-sidebar-scrim\s*\{[^}]*z-index:420",
        css,
        re.S,
    )
    assert re.search(
        r"\.iu-shell\.iu-shell--mobile-menu-open\s+\.iu-mobile\s*\{\s*display:none!important",
        css,
        re.S,
    )
