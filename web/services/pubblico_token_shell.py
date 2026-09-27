"""Pagine React pubbliche con link personale: portale del cliente e pagamento.

Le pagine non hanno la cornice dello studio: una shell minima monta
`PortaleTokenApp` o `PagamentoLinkApp`, che leggono i dati dalle API
`/api/v1/pubblico/...`. La vista classica resta con `?_legacy=1`.
Il token è già nell'indirizzo; la shell lo ripete solo come attributo della
radice React e non contiene altri dati del cliente.
"""

from __future__ import annotations

from typing import Any

from flask import get_flashed_messages, make_response, render_template, request

from web.services.piattaforma_shell_runtime import vista_classica_richiesta

COMPONENTE_PORTALE = "src/components/PortaleTokenApp.tsx"
COMPONENTE_PAGAMENTO = "src/components/PagamentoLinkApp.tsx"

__all__ = [
    "render_pagamento_shell",
    "render_portale_token_shell",
    "vista_classica_richiesta",
]


def _asset_react(componente: str) -> dict[str, Any]:
    """Entry React e solo i file del componente pubblico (niente pagine dello studio)."""
    from web.blueprints.react_shell import _cached_route_assets, _load_manifest, _react_static_dir, _vite_entry

    assets = _vite_entry("")
    if not assets.get("ready"):
        return assets
    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest:
        extra = _cached_route_assets(manifest_path, manifest, componente)
        assets["preload_js"] = extra["js"]
        assets["page_css"] = extra["css"]
    return assets


def _messaggi_in_attesa() -> list[dict[str, str]]:
    """Messaggi lasciati da una pagina classica (es. dopo un modulo storico)."""
    return [{"categoria": str(c), "testo": str(m)} for c, m in get_flashed_messages(with_categories=True)]


def _risposta(template: str, status: int, **contesto: Any):
    response = make_response(render_template(template, **contesto), status)
    # Pagine legate al link del cliente: niente cache condivise.
    response.headers["Cache-Control"] = "no-store"
    return response


def render_portale_token_shell(token: str, sezione: str, *, titolo: str, studio_nome: str, status: int = 200, stato: str = ""):
    return _risposta(
        "portale_token_shell.html",
        status,
        react_assets=_asset_react(COMPONENTE_PORTALE),
        token=token,
        sezione=sezione,
        stato=stato,
        titolo=titolo,
        studio_nome=studio_nome,
        messaggi=_messaggi_in_attesa(),
        percorso_classico=request.path,
    )


def render_pagamento_shell(token: str, vista: str, *, titolo: str, studio_nome: str, status: int = 200, provider: str = ""):
    return _risposta(
        "pagamento_link_shell.html",
        status,
        react_assets=_asset_react(COMPONENTE_PAGAMENTO),
        token=token,
        vista=vista,
        provider=provider,
        titolo=titolo,
        studio_nome=studio_nome,
        messaggi=_messaggi_in_attesa(),
        percorso_classico=request.path,
    )
