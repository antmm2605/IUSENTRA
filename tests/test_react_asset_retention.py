import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "web" / "static" / "react" / "assets"


def test_vite_preserva_il_code_splitting_delle_route_react():
    config = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")

    assert "inlineDynamicImports" not in config
    assert "cssCodeSplit: true" in config
    assert "enforceBundleBudget" in config
    assert "maxBytes = 500_000" in config
    assert "return 'vendor-react'" in config
    assert "return 'vendor-icons'" in config
    assert "lazyPage(() => import(" in (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")


def test_manifest_react_corrente_rispetta_budget_500kb_per_js_e_css():
    manifest_path = ROOT / "web" / "static" / "react" / ".vite" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    oversized: list[str] = []

    for entry in manifest.values():
        paths = [entry.get("file"), *(entry.get("css") or [])]
        for relative in paths:
            if not relative or Path(relative).suffix not in {".js", ".css"}:
                continue
            asset = ROOT / "web" / "static" / "react" / str(relative)
            if asset.stat().st_size > 500_000:
                oversized.append(f"{relative}: {asset.stat().st_size} byte")

    assert not oversized, "Budget asset React superato: " + ", ".join(sorted(set(oversized)))


def test_react_bundles_refer_to_existing_assets():
    """Cached React shells and lazy chunks must keep loading after deploy."""

    index_chunks = sorted(ASSETS_DIR.glob("index-*.js"))
    assert index_chunks, "Nessun bundle React index trovato"

    missing: list[str] = []
    reference_pattern = re.compile(r"""["']\./([^"']+\.(?:js|css))["']""")
    for chunk in sorted(ASSETS_DIR.glob("*.js")):
        source = chunk.read_text(encoding="utf-8", errors="ignore")
        for relative in reference_pattern.findall(source):
            if not (ASSETS_DIR / relative).exists():
                missing.append(f"{chunk.name} -> {relative}")

    assert not missing, "Asset React mancanti per bundle in cache: " + ", ".join(missing[:20])


def test_telematico_surface_bundle_contiene_copia_pst_aggiornata():
    manifest_path = ROOT / "web" / "static" / "react" / ".vite" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = manifest.get("src/components/TelematicoSurfacePage.tsx") or {}
    entry_file = entry.get("file") or (manifest.get("index.html") or {}).get("file") or ""
    chunk = ROOT / "web" / "static" / "react" / str(entry_file)
    assert chunk.is_file(), "Chunk TelematicoSurfacePage assente dal bundle React pubblicato"

    source = chunk.read_text(encoding="utf-8", errors="ignore")
    assert "Default PST: copia di consultazione" in source
    assert "dopo il tentativo di avvio automatico" in source
    assert "Timeout del Local Signer locale" not in source
