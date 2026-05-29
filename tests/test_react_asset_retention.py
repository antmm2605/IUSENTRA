import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "web" / "static" / "react" / "assets"


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
    chunk = ROOT / "web" / "static" / "react" / str(entry.get("file") or "")
    assert chunk.exists(), "Chunk TelematicoSurfacePage assente dal bundle React pubblicato"

    source = chunk.read_text(encoding="utf-8", errors="ignore")
    assert "Ricerca PST in corso" in source
    assert "Timeout del Local Signer locale" not in source
