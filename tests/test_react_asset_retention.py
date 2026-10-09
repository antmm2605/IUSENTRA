import json
import re
import subprocess
import shutil
import pytest
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


def test_vite_pruning_preserva_release_in_cache_e_limita_lo_storico():
    source = (ROOT / "frontend" / "vite" / "pruneReactAssets.ts").read_text(encoding="utf-8")

    assert "MAX_PREEXISTING_ASSETS_TO_RETAIN = 400" in source
    assert "existingAssets.length <= MAX_PREEXISTING_ASSETS_TO_RETAIN" in source
    assert "previousAssets.add(entry.name)" in source
    assert "new Set([...previousAssets, ...currentAssets])" in source
    assert "dirname(target) !== assetsDir" in source
    assert "['ls-files', '-z', '--', assetsDir]" in source
    assert "previousAssets.add(basename(trackedPath))" in source

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    seed = "COPY web/static/react ./web/static/react"
    build = "pnpm --filter @iusentra/studio build:vite"
    assert seed in dockerfile
    assert dockerfile.index(seed) < dockerfile.index(build)


def test_tutti_gli_asset_pubblicati_restano_disponibili_dopo_build_intermedie():
    published = subprocess.check_output(
        ["git", "ls-files", "-z", "--", "web/static/react/assets"], cwd=ROOT,
    ).decode("utf-8").split("\0")
    missing = [relative for relative in published if relative and not (ROOT / relative).is_file()]
    assert not missing, "Asset pubblicati cancellati: " + ", ".join(missing[:20])


@pytest.mark.parametrize("git_available", [True, False])
def test_build_ripetute_preservano_asset_pubblicati_oltre_la_soglia(tmp_path, git_available):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    asset_dir = tmp_path / "web/static/react/assets"
    asset_dir.mkdir(parents=True)
    published = asset_dir / "index-PUBLISHED.js"
    published.write_text("export default 1", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    # La soglia del vecchio comportamento causava la perdita del rilascio.
    for index in range(401):
        (asset_dir / f"draft-{index:08d}.js").write_text("", encoding="utf-8")
    plugin_url = (ROOT / "frontend/vite/pruneReactAssets.ts").as_uri()
    script = f"""
        import {{ pruneReactAssets }} from {json.dumps(plugin_url)};
        import {{ writeFile, mkdir, access }} from 'node:fs/promises';
        import {{ join }} from 'node:path';
        const root = {json.dumps(str(tmp_path))};
        const out = join(root, 'web/static/react');
        await mkdir(join(out, '.vite'));
        if (!{str(git_available).lower()}) process.env.PATH = '';
        for (const name of ['index-FIRSTNEW.js', 'index-SECONDNEW.js']) {{
            const plugin = pruneReactAssets();
            plugin.configResolved({{root, build: {{outDir: out}}, logger: {{info() {{}}}}}});
            await plugin.buildStart();
            await writeFile(join(out, 'assets', name), 'export default 2');
            plugin.generateBundle({{}}, {{chunk: {{fileName: 'assets/' + name}}}});
            await writeFile(join(out, '.vite/manifest.json'), JSON.stringify({{index: {{file: 'assets/' + name}}}}));
            await plugin.closeBundle();
            await access(join(out, 'assets/index-PUBLISHED.js'));
        }}
    """
    subprocess.run([shutil.which("node"), "--experimental-strip-types", "--input-type=module", "-e", script],
                   check=True, capture_output=True, text=True, timeout=30)
    assert published.read_text(encoding="utf-8") == "export default 1"
    assert (asset_dir / "index-FIRSTNEW.js").exists()


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


@pytest.mark.parametrize("phase", ["buildEnd", "generateBundle"])
def test_build_fallita_non_pulisce_asset_ne_maschera_errore(tmp_path, phase):
    asset_dir = tmp_path / "web/static/react/assets"
    asset_dir.mkdir(parents=True)
    published = asset_dir / "index-PUBLISHED.js"
    published.write_text("rilascio in uso", encoding="utf-8")
    plugin_url = (ROOT / "frontend/vite/pruneReactAssets.ts").as_uri()
    script = f"""
        import {{ pruneReactAssets }} from {json.dumps(plugin_url)};
        import {{ access }} from 'node:fs/promises';
        const plugin = pruneReactAssets();
        plugin.configResolved({{root: {json.dumps(str(tmp_path))},
            build: {{outDir: 'web/static/react'}}, logger: {{info() {{}}}}}});
        await plugin.buildStart();
        plugin.buildEnd({json.dumps(phase)} === 'buildEnd' ? new Error('difetto primario') : undefined);
        // Il plugin precedente può fallire prima di generateBundle del pulitore.
        await plugin.closeBundle();
        await access({json.dumps(str(published))});
    """
    subprocess.run([shutil.which("node"), "--experimental-strip-types", "--input-type=module", "-e", script],
                   check=True, capture_output=True, text=True, timeout=30)
    assert published.read_text(encoding="utf-8") == "rilascio in uso"
