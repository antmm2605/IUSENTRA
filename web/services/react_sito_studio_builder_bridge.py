"""Bridge React operativo per il Builder Sito Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from werkzeug.datastructures import FileStorage

from pct.studio_site import slugify
from pct.studio_site_blocks import normalize_blocks
from web.services.studio_site_assets import delete_builder_asset, save_builder_asset
from web.services.studio_site_builder_runtime import (
    apply_theme_template,
    build_builder_payload,
    generate_automatic_site,
    publish_page_blocks,
    restore_design_revision,
    save_design_settings,
    save_page_blocks,
    validate_site_builder,
)
from web.services.studio_site_runtime import get_site_for_current_tenant, studio_site_repository


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any, limit: int = 0) -> str:
    text = " ".join(str(value or "").split())
    if limit and len(text) > limit:
        return text[: limit - 1].rstrip() + "..."
    return text


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bool(value: Any) -> bool:
    return bool(value)


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "azioni_protette",
        "route_owner": "react_shell",
        "operational": True,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/sito-studio__builder.json",
    }


def _status_label(status: Any, *, home: bool = False) -> str:
    if home:
        return "Home"
    clean = _text(status).lower()
    return {
        "published": "Pubblicata",
        "draft": "Bozza",
        "archived": "Archiviata",
    }.get(clean, clean.title() if clean else "Bozza")


def _site(site: dict[str, Any], public_url: str) -> dict[str, Any]:
    return {
        "id": _int(site.get("id")),
        "studioName": _text(site.get("studio_nome")),
        "siteName": _text(site.get("site_name") or site.get("studio_nome") or "Sito Studio"),
        "title": _text(site.get("site_title")),
        "description": _text(site.get("site_description"), 360),
        "claim": _text(site.get("hero_claim"), 180),
        "publicSlug": _text(site.get("public_slug")),
        "published": _bool(site.get("is_published")),
        "active": _bool(site.get("is_active")),
        "themeTemplate": _text(site.get("theme_template")),
        "updatedAt": _text(site.get("updated_at")),
        "publicUrl": _text(public_url),
    }


def _page(row: dict[str, Any]) -> dict[str, Any]:
    page_id = _int(row.get("id"))
    blocks = normalize_blocks(row.get("body_json") or [])
    return {
        "id": page_id,
        "title": _text(row.get("title") or "Pagina senza titolo"),
        "slug": _text(row.get("slug")),
        "excerpt": _text(row.get("excerpt"), 180),
        "status": _text(row.get("status") or "draft"),
        "statusLabel": _status_label(row.get("status"), home=_bool(row.get("is_home"))),
        "home": _bool(row.get("is_home")),
        "showInMenu": _bool(row.get("show_in_menu")),
        "blocksCount": len(blocks),
        "updatedAt": _text(row.get("updated_at") or row.get("created_at")),
        "href": f"/sito-studio/builder?page_id={page_id}" if page_id else "/sito-studio/builder",
    }


def _template(row: dict[str, Any], active_code: str) -> dict[str, Any]:
    code = _text(row.get("code"))
    return {
        "code": code,
        "name": _text(row.get("name") or code or "Modello grafico"),
        "description": _text(row.get("description"), 220),
        "active": bool(code and code == active_code),
    }


def _preset(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": _text(row.get("type")),
        "label": _text(row.get("label") or row.get("type") or "Blocco"),
        "defaults": row.get("defaults") if isinstance(row.get("defaults"), dict) else {},
    }


def _asset(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _int(row.get("id")),
        "title": _text(row.get("title") or row.get("original_filename") or "Immagine"),
        "url": _text(row.get("url")),
        "altText": _text(row.get("alt_text")),
        "category": _text(row.get("category")),
        "createdAt": _text(row.get("created_at")),
    }


def _revision(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _int(row.get("id")),
        "label": _text(row.get("label") or "Revisione"),
        "createdAt": _text(row.get("created_at")),
        "createdBy": _text(row.get("created_by")),
    }


def _validation_group(group_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {
        "seo": "Ricerca e anteprima",
        "accessibility": "Accessibilita",
        "privacy": "Privacy",
        "deontology": "Deontologia",
    }
    items = []
    for row in rows:
        severity = _text(row.get("severity") or "info").lower()
        items.append(
            {
                "severity": severity if severity in {"error", "warning", "info"} else "info",
                "message": _text(row.get("message") or row.get("suggestion") or "Controllo disponibile."),
            }
        )
    return {"id": group_id, "label": labels.get(group_id, group_id.title()), "items": items}


def _validation(raw: dict[str, Any]) -> dict[str, Any]:
    groups = [
        _validation_group(group_id, list(raw.get(group_id) or []))
        for group_id in ("seo", "accessibility", "privacy", "deontology")
    ]
    return {
        "groups": groups,
        "generatedAt": _text(raw.get("generated_at")),
        "issues": sum(len(group["items"]) for group in groups),
        "blocking": sum(1 for group in groups for item in group["items"] if item["severity"] == "error"),
    }


def _theme(raw: dict[str, Any], site: dict[str, Any]) -> dict[str, Any]:
    typography = raw.get("typography") if isinstance(raw.get("typography"), dict) else {}
    tokens = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else {}
    layout = raw.get("layout") if isinstance(raw.get("layout"), dict) else {}
    effects = raw.get("effects") if isinstance(raw.get("effects"), dict) else {}
    return {
        "templateCode": _text(site.get("theme_template") or raw.get("template")),
        "tokens": {str(key): _text(value) for key, value in tokens.items()},
        "typography": {str(key): _text(value) for key, value in typography.items()},
        "layout": {str(key): _text(value) for key, value in layout.items()},
        "effects": {str(key): _text(value) for key, value in effects.items()},
    }


def _builder_payload(page_id: int | None = None) -> dict[str, Any]:
    raw = build_builder_payload(page_id=page_id)
    site = raw.get("site") or {}
    active_page = raw.get("active_page") or {}
    active_id = _int(active_page.get("id"))
    active_template = _text(site.get("theme_template"))
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "site": _site(site, _text(raw.get("public_url"))),
        "theme": _theme(raw.get("theme") or {}, site),
        "templates": [_template(row, active_template) for row in list(raw.get("templates") or [])],
        "blockPresets": [_preset(row) for row in list(raw.get("block_presets") or [])],
        "pages": [_page(row) for row in list(raw.get("pages") or [])],
        "activePage": _page(active_page) if active_page else {},
        "activePageId": active_id,
        "activeBlocks": normalize_blocks(raw.get("active_blocks") or []),
        "assets": [_asset(row) for row in list(raw.get("assets") or [])],
        "revisions": [_revision(row) for row in list(raw.get("revisions") or [])],
        "validation": _validation(raw.get("validation") or {}),
        "publicUrl": _text(raw.get("public_url")),
        "activePreviewUrl": _text(raw.get("active_preview_url") or raw.get("public_url")),
        "previewUrl": _text(raw.get("preview_url")),
    }


def build_react_sito_studio_builder_payload(page_id: int | None = None) -> dict[str, Any]:
    return _builder_payload(page_id=page_id)


def builder_error_payload(message: str = "Builder Sito Studio non disponibile.") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "site": {},
        "theme": {},
        "templates": [],
        "blockPresets": [],
        "pages": [],
        "activePage": {},
        "activePageId": 0,
        "activeBlocks": [],
        "assets": [],
        "revisions": [],
        "validation": {"groups": [], "generatedAt": "", "issues": 0, "blocking": 0},
        "publicUrl": "",
        "activePreviewUrl": "",
        "previewUrl": "",
        "message": message,
    }


def apply_react_builder_template(payload: dict[str, Any]) -> dict[str, Any]:
    code = _text(payload.get("template_code") or payload.get("templateCode"))
    if not code:
        return {"ok": False, "message": "Seleziona un modello grafico."}
    apply_theme_template(code)
    return {"ok": True, "message": "Modello grafico applicato.", "payload": _builder_payload()}


def save_react_builder_design(payload: dict[str, Any]) -> dict[str, Any]:
    save_design_settings(payload or {})
    return {"ok": True, "message": "Parametri grafici salvati.", "payload": _builder_payload()}


def generate_react_builder_site(payload: dict[str, Any]) -> dict[str, Any]:
    generated = generate_automatic_site(payload or {})
    page_id = _int((generated.get("active_page") or {}).get("id")) if isinstance(generated, dict) else None
    return {"ok": True, "message": "Sito predisposto in bozza.", "payload": _builder_payload(page_id=page_id)}


def validate_react_builder() -> dict[str, Any]:
    return {"ok": True, "message": "Controlli completati.", "validation": _validation(validate_site_builder())}


def create_react_builder_page(payload: dict[str, Any]) -> dict[str, Any]:
    title = _text(payload.get("title"))
    if not title:
        return {"ok": False, "message": "Indica il titolo della nuova pagina."}
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    existing_pages = repo.list_pages(site_id)
    page = repo.save_page(
        site_id,
        {
            "title": title,
            "slug": slugify(_text(payload.get("slug")) or title),
            "excerpt": _text(payload.get("excerpt"), 220),
            "body_json": [],
            "status": "draft",
            "show_in_menu": _bool(payload.get("showInMenu", True)),
            "sort_order": len(existing_pages) + 1,
            "is_home": False,
            "seo_title": title,
            "seo_description": _text(payload.get("excerpt"), 220),
        },
    )
    page_id = _int((page or {}).get("id"))
    return {"ok": True, "message": "Pagina creata in bozza.", "page": _page(page or {}), "payload": _builder_payload(page_id=page_id)}


def delete_react_builder_page(page_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    page = repo.get_page(site_id, int(page_id))
    if page is None:
        return {"ok": False, "message": "Pagina non trovata."}
    if _bool(page.get("is_home")):
        return {"ok": False, "message": "La pagina principale non puo essere eliminata."}
    repo.delete_page(site_id, int(page_id))
    return {"ok": True, "message": "Pagina rimossa.", "payload": _builder_payload()}


def save_react_builder_blocks(page_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    blocks = normalize_blocks(payload.get("blocks") or [])
    page = save_page_blocks(int(page_id), blocks)
    return {
        "ok": True,
        "message": "Bozza pagina salvata.",
        "page": _page(page),
        "blocks": normalize_blocks(page.get("body_json") or blocks),
        "payload": _builder_payload(page_id=int(page_id)),
    }


def publish_react_builder_blocks(page_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    blocks = normalize_blocks(payload.get("blocks") or [])
    page = publish_page_blocks(int(page_id), blocks)
    return {
        "ok": True,
        "message": "Modifiche pubblicate.",
        "page": _page(page),
        "blocks": normalize_blocks(page.get("body_json") or blocks),
        "payload": _builder_payload(page_id=int(page_id)),
    }


def restore_react_builder_revision(revision_id: int) -> dict[str, Any]:
    restore_design_revision(int(revision_id))
    return {"ok": True, "message": "Revisione ripristinata.", "payload": _builder_payload()}


def upload_react_builder_asset(file: FileStorage | None, payload: dict[str, Any]) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    asset = save_builder_asset(site, file, payload=payload or {})
    return {"ok": True, "message": "Immagine caricata.", "asset": _asset(asset), "payload": _builder_payload()}


def delete_react_builder_asset(asset_id: int) -> dict[str, Any]:
    site = get_site_for_current_tenant()
    delete_builder_asset(site, int(asset_id))
    repo = studio_site_repository()
    assets = [_asset(row) for row in repo.list_assets(int(site["id"]), limit=120)]
    return {"ok": True, "message": "Immagine rimossa.", "assets": assets}
