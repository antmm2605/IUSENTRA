"""Risposte del sito pubblico dello studio con React pre-generato e pre-generazione dopo i salvataggi."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import Flask, current_app, make_response, render_template, request

from web.services.sito_pubblico_dati import dati_pagina
from web.services.sito_pubblico_prerender import pagina_pre_generata, pre_genera_in_sfondo

COMPONENTE_SITO = "src/sitoPubblico/idrataSito.tsx"
PREFISSI_SCRITTURA = ("/sito-studio/", "/api/v1/ui/sito-studio/")


def cartella_cache(public_slug: str) -> Path:
    from web.services.studio_site_runtime import studio_site_assets_root

    slug = "".join(c for c in str(public_slug) if c.isalnum() or c in "-_") or "sito"
    return studio_site_assets_root().parent / "site_prerender" / slug


def json_sicuro(dati: dict[str, Any]) -> str:
    """JSON da scrivere in uno <script type="application/json">: < > & codificati, nessuna chiusura del tag."""
    corpo = json.dumps(dati, ensure_ascii=False)
    return corpo.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _asset_sito() -> dict[str, Any]:
    from web.blueprints.react_shell import _cached_route_assets, _load_manifest, _react_static_dir, _vite_entry

    assets = _vite_entry("/")
    if not assets.get("ready"):
        return assets
    manifest_path = _react_static_dir() / ".vite" / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if manifest and COMPONENTE_SITO in manifest:
        route = _cached_route_assets(manifest_path, manifest, COMPONENTE_SITO)
        assets["page_css"] = route["css"]
    return assets


def risposta_sito(payload: dict[str, Any], vista: str, *, titolo: str, descrizione: str = "",
                  pagina: dict[str, Any] | None = None, articolo: dict[str, Any] | None = None):
    dati = dati_pagina(payload, vista, pagina=pagina, articolo=articolo)
    html = pagina_pre_generata(cartella_cache(payload["site"]["public_slug"]), dati) or ""
    corpo = render_template(
        "studio_site/sito_pubblico_shell.html",
        payload=payload,
        titolo=titolo,
        descrizione=descrizione or payload["site"].get("site_description") or "",
        html_pre_generato=html,
        dati_json=json_sicuro(dati),
        react_assets=_asset_sito(),
    )
    return make_response(corpo)


def pagine_del_sito(public_slug: str) -> list[dict[str, Any]]:
    """Tutte le pagine pubbliche (contenuti pubblicati) da pre-generare per il sito."""
    from web.services.studio_site_runtime import build_public_site_payload, studio_site_repository

    payload = build_public_site_payload(public_slug, include_drafts=False)
    repo = studio_site_repository()
    site_id = int(payload["site"]["id"])
    pagine: list[dict[str, Any]] = []
    if payload.get("home_page"):
        pagine.append(dati_pagina(payload, "home"))
    for riga in repo.list_pages(site_id, published_only=True):
        pagina = repo.get_page_by_slug(site_id, str(riga.get("slug") or ""), published_only=True)
        if pagina:
            pagine.append(dati_pagina(payload, "pagina", pagina=pagina))
    pagine.append(dati_pagina(payload, "articoli"))
    for riga in payload.get("articles") or []:
        articolo = repo.get_article_by_slug(site_id, str(riga.get("slug") or ""), published_only=True)
        if articolo:
            pagine.append(dati_pagina(payload, "articolo", articolo=articolo))
    pagine.append(dati_pagina(payload, "contatti"))
    if payload.get("booking_enabled"):
        pagine.append(dati_pagina(payload, "prenota"))
    for vista, chiave in (("strumenti-legali", "show_legal_tools"), ("applicazioni", "show_applications"), ("news-giuridiche", "show_legal_news")):
        if payload["site"].get(chiave):
            pagine.append(dati_pagina(payload, vista))
    return pagine


def registra_pregenerazione(app: Flask) -> None:
    """Dopo ogni salvataggio riuscito dei contenuti del sito, pre-genera le pagine pubbliche in sfondo."""

    @app.after_request
    def _pre_genera_dopo_salvataggio(response):
        if request.method in {"GET", "HEAD", "OPTIONS"} or response.status_code >= 400:
            return response
        if not request.path.startswith(PREFISSI_SCRITTURA):
            return response
        try:
            from web.services.studio_site_runtime import ensure_current_studio_site

            site = ensure_current_studio_site()
            if site.get("is_published") and site.get("is_active"):
                slug = str(site["public_slug"])
                pre_genera_in_sfondo(cartella_cache(slug), pagine_del_sito(slug))
        except Exception:  # la pre-generazione non deve mai far fallire il salvataggio
            current_app.logger.warning("Sito pubblico: pre-generazione dopo il salvataggio non avviata", exc_info=True)
        return response


__all__ = ["cartella_cache", "json_sicuro", "pagine_del_sito", "registra_pregenerazione", "risposta_sito"]
