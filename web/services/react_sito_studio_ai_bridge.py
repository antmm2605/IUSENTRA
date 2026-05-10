"""Bridge React operativo per Redazione AI del Sito Studio."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web.services.studio_site_ai_runtime import (
    create_article_draft_from_job,
    generate_ai_article_job,
    generate_article_cover,
    publish_ai_article,
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


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "azioni_protette",
        "route_owner": "react_shell",
        "operational": True,
        "legacy_contract": "artifacts/react-migration/legacy-contracts/sito-studio__redazione-ai.json",
    }


def _status_label(status: Any) -> str:
    clean = _text(status).lower()
    return {
        "draft_generated": "Bozza generata",
        "draft_created": "Articolo creato",
        "draft": "Bozza",
        "published": "Pubblicato",
        "archived": "Archiviato",
    }.get(clean, "Da rivedere" if clean else "Da rivedere")


def _severity_label(severity: Any) -> str:
    clean = _text(severity).lower()
    return {"error": "Blocco", "warning": "Da rivedere", "info": "Nota"}.get(clean, "Nota")


def _risk(row: dict[str, Any]) -> dict[str, str]:
    area = _text(row.get("area")).replace("_", " ")
    return {
        "area": area.title() if area else "Controllo",
        "severity": _text(row.get("severity")).lower(),
        "severityLabel": _severity_label(row.get("severity")),
        "message": _text(row.get("message") or row.get("suggestion"), 260),
        "suggestion": _text(row.get("suggestion"), 260),
    }


def _job(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result_json") if isinstance(row.get("result_json"), dict) else {}
    risks = [_risk(item) for item in list(row.get("risk_checklist_json") or []) if isinstance(item, dict)]
    return {
        "id": _int(row.get("id")),
        "topic": _text(row.get("topic")),
        "title": _text(result.get("title") or row.get("topic") or "Bozza articolo"),
        "excerpt": _text(result.get("excerpt"), 360),
        "statusLabel": _status_label(row.get("status")),
        "articleId": _int(row.get("article_id")),
        "createdAt": _text(row.get("created_at")),
        "createdBy": _text(row.get("created_by")),
        "risks": risks,
        "draftAvailable": not _int(row.get("article_id")),
    }


def _article(row: dict[str, Any]) -> dict[str, Any]:
    article_id = _int(row.get("id"))
    return {
        "id": article_id,
        "title": _text(row.get("title") or "Articolo senza titolo"),
        "excerpt": _text(row.get("excerpt"), 360),
        "category": _text(row.get("category")) or "Senza categoria",
        "statusLabel": _status_label(row.get("status")),
        "published": _text(row.get("status")).lower() == "published",
        "coverUrl": _text(row.get("cover_url")),
        "updatedAt": _text(row.get("updated_at") or row.get("created_at")),
        "editHref": f"/sito-studio/articoli/{article_id}/modifica" if article_id else "/sito-studio",
    }


def _site(site: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _int(site.get("id")),
        "siteName": _text(site.get("site_name") or site.get("studio_nome") or "Sito Studio"),
        "studioName": _text(site.get("studio_nome")),
        "publicSlug": _text(site.get("public_slug")),
    }


def _payload() -> dict[str, Any]:
    site = get_site_for_current_tenant()
    repo = studio_site_repository()
    site_id = int(site["id"])
    jobs = [_job(row) for row in repo.list_ai_article_jobs(site_id, limit=30)]
    articles = [_article(row) for row in repo.list_articles(site_id, limit=40)]
    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "site": _site(site),
        "jobs": jobs,
        "articles": articles,
        "summary": {
            "jobs": len(jobs),
            "articles": len(articles),
            "drafts": sum(1 for article in articles if not article["published"]),
            "published": sum(1 for article in articles if article["published"]),
            "checks": sum(len(job["risks"]) for job in jobs),
        },
        "actions": {
            "builder": "/sito-studio/builder",
            "dashboard": "/sito-studio",
            "publicSite": "/sito-studio/pubblico",
        },
    }


def build_react_sito_studio_ai_payload() -> dict[str, Any]:
    return _payload()


def build_react_sito_studio_ai_error_payload(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(),
        "site": {},
        "jobs": [],
        "articles": [],
        "summary": {"jobs": 0, "articles": 0, "drafts": 0, "published": 0, "checks": 0},
        "actions": {"builder": "/sito-studio/builder", "dashboard": "/sito-studio", "publicSite": "/sito-studio"},
        "message": message,
    }


def generate_react_sito_studio_ai_article(payload: dict[str, Any]) -> dict[str, Any]:
    generate_ai_article_job(payload or {})
    return {"ok": True, "message": "Bozza assistita generata e pronta per la revisione.", "payload": _payload()}


def create_react_sito_studio_ai_draft(job_id: int) -> dict[str, Any]:
    create_article_draft_from_job(int(job_id))
    return {"ok": True, "message": "Articolo creato in bozza.", "payload": _payload()}


def generate_react_sito_studio_ai_image(article_id: int) -> dict[str, Any]:
    generate_article_cover(int(article_id))
    return {"ok": True, "message": "Immagine associata all'articolo.", "payload": _payload()}


def publish_react_sito_studio_ai_article(article_id: int) -> dict[str, Any]:
    publish_ai_article(int(article_id))
    return {"ok": True, "message": "Articolo pubblicato dopo revisione.", "payload": _payload()}
