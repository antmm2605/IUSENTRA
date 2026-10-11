"""Cached build assets for native interfaces sharing the activity lifecycle."""

from markupsafe import Markup, escape

ENTRIES = frozenset({
    "mobile-pdf-viewer.js", "admin_coverage_review.js", "global-search.js", "studio_site_builder.js",
})


def native_activity_assets(filename: str) -> Markup:
    if filename not in ENTRIES:
        raise ValueError("Interfaccia nativa non prevista.")
    from web.blueprints.react_shell import _cached_route_assets, _load_manifest, _react_static_dir

    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    manifest = _load_manifest(manifest_path) or {}
    key = f"../web/static/js/{filename}"
    entry = manifest.get(key) or {}
    if not entry.get("file"):
        raise RuntimeError("Build dell'interfaccia non disponibile: ricostruire gli asset dell'applicazione.")
    assets = _cached_route_assets(manifest_path, manifest, key)
    styles = "".join(f'<link rel="stylesheet" href="{escape(url)}">' for url in assets["css"])
    return Markup(f'{styles}<script type="module" src="/static/react/{escape(entry["file"])}"></script>')
