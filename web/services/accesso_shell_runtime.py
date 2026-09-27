"""Pagina pubblica di accesso servita dall'applicazione React (``AccessoApp``).

Accesso, verifica in due passaggi e cambio obbligatorio della password non
usano la cornice dello studio: una pagina minima monta ``AccessoApp`` con la
vista richiesta. Le pagine Jinja storiche restano raggiungibili con
``?_legacy=1`` finché non si eliminano.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from flask import make_response, render_template, request

from web.services.auth_accesso_flow import destinazione_sicura

VISTE_ACCESSO = frozenset({"login", "2fa", "password"})
COMPONENTE_ACCESSO = "src/components/AccessoApp.tsx"
_VALORI_LEGACY = {"1", "true", "si", "yes", "on"}


def vista_classica_accesso_richiesta() -> bool:
    return (request.args.get("_legacy") or "").strip().lower() in _VALORI_LEGACY


def _asset_accesso() -> dict[str, Any]:
    """Entry React con i soli chunk di ``AccessoApp`` da precaricare."""
    from web.blueprints.react_shell import _cached_route_assets, _load_manifest, _react_static_dir, _vite_entry

    # "/" non corrisponde a nessuna pagina dello studio: nessun precaricamento estraneo.
    assets = _vite_entry("/")
    if not assets.get("ready"):
        return assets
    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest and COMPONENTE_ACCESSO in manifest:
        route = _cached_route_assets(manifest_path, manifest, COMPONENTE_ACCESSO)
        assets["preload_js"] = route["js"]
        assets["page_css"] = route["css"]
    return assets


def _url_vista_classica() -> str:
    query = request.args.to_dict(flat=True)
    query["_legacy"] = "1"
    return f"{request.path}?{urlencode(query)}"


def render_accesso_shell(vista: str, *, titolo: str):
    """Pagina React di accesso. La vista è decisa dal server, non dal client."""
    if vista not in VISTE_ACCESSO:  # pragma: no cover - guardrail di chiamata
        raise ValueError(f"Vista di accesso non prevista: {vista}")
    html = render_template(
        "accesso_shell.html",
        react_assets=_asset_accesso(),
        vista=vista,
        titolo=titolo,
        next_sicuro=destinazione_sicura(request.args.get("next", "")),
        sessione_scaduta=bool(request.args.get("timeout")),
        url_vista_classica=_url_vista_classica(),
    )
    response = make_response(html, 200)
    # La pagina contiene il token CSRF della sessione anonima: mai in cache.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


__all__ = ["VISTE_ACCESSO", "render_accesso_shell", "vista_classica_accesso_richiesta"]
