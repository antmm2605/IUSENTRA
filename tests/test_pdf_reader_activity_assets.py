"""The native reader shares activity owners without loading the React runtime."""

import json
from pathlib import Path
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]


def test_native_reader_bundle_has_only_activity_dependencies():
    manifest = json.loads((ROOT / "web/static/react/.vite/manifest.json").read_text(encoding="utf-8"))
    entry = manifest["../web/static/js/mobile-pdf-viewer.js"]
    pending = [entry]
    seen = set()
    files = []
    styles = []
    while pending:
        asset = pending.pop()
        name = asset["file"]
        if name in seen:
            continue
        seen.add(name)
        files.append(name)
        styles.extend(asset.get("css", []))
        pending.extend(manifest[key] for key in asset.get("imports", []))
    assert not any("vendor-react" in name or "vendor-icons" in name for name in files)
    assert any("activity-" in name for name in styles)
    assert sum((ROOT / "web/static/react" / name).stat().st_size for name in files) < 25000


def test_native_asset_registry_rejects_unknown_scripts_and_resolves_styles(monkeypatch):
    import importlib
    import pytest
    from web.services.native_activity_assets import ENTRIES, native_activity_assets

    shell = importlib.import_module("web.blueprints.react_shell")
    monkeypatch.setattr(shell, "_react_static_dir", lambda: ROOT / "web/static/react")

    with pytest.raises(ValueError):
        native_activity_assets("../untrusted.js")
    with Flask(__name__).app_context():
        for filename in ENTRIES:
            markup = str(native_activity_assets(filename))
            assert '<script type="module" src="/static/react/assets/' in markup
            assert 'href="/static/react/assets/activity-' in markup
            assert 'vendor-react' not in markup


def test_native_reader_activity_owns_actual_settlement():
    source = (ROOT / "web/static/js/mobile-pdf-viewer.js").read_text(encoding="utf-8")
    assert ".finally(() => { finishOcrActivity(); ocrActive -= 1; runOcr() })" in source
    assert "window.clearTimeout(timeout)\n      finishPrintActivity()" in source
    assert "saveRotation.dataset.busy = 'false'\n      finishRotationActivity()" in source
    assert "image.removeEventListener('error', settled)" in source
    assert "if (image.complete) settled()" in source
    # A browser-owned download handoff is not reported as completed by a timer.
    download = source.split("downloadLink?.addEventListener('click'", 1)[1].split("pages.addEventListener", 1)[0]
    assert "beginActivity" not in download
    assert "Download avviato" in download


def test_shell_selects_app_entry_with_reader_first(tmp_path, monkeypatch):
    import importlib

    shell = importlib.import_module("web.blueprints.react_shell")
    (tmp_path / ".vite").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_text("const app = true;", encoding="utf-8")
    manifest = {
        "../web/static/js/mobile-pdf-viewer.js": {"file": "assets/reader.js", "isEntry": True},
        "index.html": {"file": "assets/app.js", "isEntry": True},
    }
    (tmp_path / ".vite/manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(shell, "_react_static_dir", lambda: tmp_path)
    with Flask(__name__).app_context():
        assets = shell._vite_entry("/strumenti-documentali")
    assert assets["entry_file"] == "/static/react/assets/app.js"
    assert assets["inline_entry_code"] == "const app = true;"
