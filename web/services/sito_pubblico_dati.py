"""Dati pubblici delle pagine del sito dello studio, passati al componente React ``SitoPubblico``.

Lo stesso oggetto è usato per la pre-generazione (Node) e per l'idratazione nel browser, ed è scritto
nella pagina: contiene **solo** i campi che le pagine mostrano (stessi dei template Jinja di prima),
mai dati interni dello studio (tenant, chiavi, impostazioni non pubbliche).
"""

from __future__ import annotations

from typing import Any

from pct.formatting import format_date_it

VISTE = ("home", "pagina", "articoli", "articolo", "contatti", "prenota", "strumenti-legali", "applicazioni", "news-giuridiche")

_CAMPI_SITO_TESTO = (
    "site_name", "site_title", "site_description", "public_slug", "logo_url", "city", "province", "address",
    "contact_phone", "contact_email", "whatsapp_number", "facebook_url", "instagram_url", "linkedin_url",
    "privacy_url", "cookie_policy_url", "accessibility_statement_url", "legal_disclaimer", "hero_claim",
)


def _t(valore: Any) -> str:
    return "" if valore is None else str(valore)


def _scegli(riga: dict[str, Any] | None, campi: tuple[str, ...]) -> dict[str, str]:
    riga = riga or {}
    return {campo: _t(riga.get(campo)) for campo in campi}


def _blocchi(valore: Any) -> list[dict[str, Any]]:
    return [blocco for blocco in (valore or []) if isinstance(blocco, dict) and blocco.get("type")]


def _pagina(riga: dict[str, Any] | None) -> dict[str, Any] | None:
    if not riga:
        return None
    return {**_scegli(riga, ("title", "slug", "excerpt")), "body_json": _blocchi(riga.get("body_json"))}


def _articolo(riga: dict[str, Any] | None) -> dict[str, Any] | None:
    if not riga:
        return None
    return {**_scegli(riga, ("title", "slug", "excerpt", "category", "cover_url")), "body_json": _blocchi(riga.get("body_json"))}


def payload_pubblico(payload: dict[str, Any]) -> dict[str, Any]:
    site = payload.get("site") or {}
    theme = payload.get("theme") or {}
    return {
        "site": {**_scegli(site, _CAMPI_SITO_TESTO), "cookie_banner_enabled": bool(site.get("cookie_banner_enabled"))},
        "menu_pages": [_scegli(riga, ("title", "slug")) for riga in payload.get("menu_pages") or []],
        "articles": [_articolo(riga) for riga in payload.get("articles") or []],
        "latest_articles": [_articolo(riga) for riga in payload.get("latest_articles") or []],
        "services": [_scegli(riga, ("title", "icon", "short_description")) for riga in payload.get("services") or []],
        "professionals": [_scegli(riga, ("full_name", "role_title", "bio", "email", "phone")) for riga in payload.get("professionals") or []],
        "offices": [
            {**_scegli(riga, ("name", "address", "city", "province", "phone", "email", "opening_hours", "map_url")),
             "id": int(riga.get("id") or 0)}
            for riga in payload.get("offices") or []
        ],
        "booking_enabled": bool(payload.get("booking_enabled")),
        "show_legal_tools": bool(payload.get("show_legal_tools")),
        "show_applications": bool(payload.get("show_applications")),
        "show_legal_news": bool(payload.get("show_legal_news")),
        "legal_tools": [_scegli(riga, ("title", "subtitle", "icon", "category")) for riga in payload.get("legal_tools") or []],
        "applications": [
            _scegli(riga, ("title", "summary", "icon", "badge", "section_title", "access_mode"))
            for riga in payload.get("applications") or []
        ],
        "legal_news": [
            {**_scegli(riga, ("title", "summary", "url", "source_name", "matter_name")),
             "publication_date": format_date_it(riga.get("publication_date")) if riga.get("publication_date") else ""}
            for riga in payload.get("legal_news") or []
        ],
        "template_code": _t(theme.get("template_code") or "classic_legal"),
    }


def dati_pagina(payload: dict[str, Any], vista: str, *, pagina: dict[str, Any] | None = None,
                articolo: dict[str, Any] | None = None) -> dict[str, Any]:
    if vista not in VISTE:
        raise ValueError(f"Vista del sito non prevista: {vista}")
    if vista == "home":
        pagina = payload.get("home_page")
    return {"vista": vista, "payload": payload_pubblico(payload), "pagina": _pagina(pagina), "articolo": _articolo(articolo)}


def chiave_pagina(dati: dict[str, Any]) -> str:
    """Nome stabile della pagina nella cache (per sito): home, pagina-<slug>, articolo-<slug>, contatti…"""
    vista = dati["vista"]
    if vista == "pagina" and dati.get("pagina"):
        return f"pagina-{dati['pagina']['slug']}"
    if vista == "articolo" and dati.get("articolo"):
        return f"articolo-{dati['articolo']['slug']}"
    return vista


__all__ = ["VISTE", "chiave_pagina", "dati_pagina", "payload_pubblico"]
