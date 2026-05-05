"""Runtime Flask per Editor AI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, session

from pct.editor_ai import EditorAIRepository, EditorAIService
from pct.template_atti import GestioneTemplateAtti
from web.helpers import get_fascicoli
from web.services.document_intelligence_runtime import build_document_ai_service
from web.services.storage_runtime import get_request_studio_db, get_request_storage_runtime


def editor_ai_fascicoli_db_path() -> str:
    if has_app_context():
        return str(
            current_app.config.get("FASCICOLI_DB")
            or current_app.config.get("FASCICOLI_DB_PATH")
            or Path(current_app.instance_path) / "fascicoli" / "fascicoli.json"
        )
    return str(Path("data") / "fascicoli" / "fascicoli.json")


def editor_ai_tenant_id() -> str:
    if has_request_context():
        tenant = getattr(g, "tenant", None)
        slug = str(getattr(tenant, "slug", "") or "").strip()
        if slug:
            return slug
        user = g.get("utente_corrente")
        user_slug = str(getattr(user, "tenant_slug", "") or session.get("tenant_slug") or "").strip()
        if user_slug:
            return user_slug
    if has_app_context():
        profile = get_request_storage_runtime(editor_ai_fascicoli_db_path())
        return profile.tenant_slug or "single-studio"
    return "single-studio"


def editor_ai_user_context() -> dict[str, Any]:
    user = g.get("utente_corrente") if has_request_context() else None
    return {
        "user": user,
        "user_id": str(getattr(user, "id", "") or getattr(user, "username", "") or ""),
    }


def build_template_repository() -> GestioneTemplateAtti:
    return GestioneTemplateAtti(
        db_path=str(current_app.config.get("TEMPLATE_ATTI_DB", "./template_atti/templates.json")),
    )


def build_editor_ai_service() -> EditorAIService:
    anchor = editor_ai_fascicoli_db_path()
    structured_db = get_request_studio_db(anchor) if has_app_context() else None
    repository = EditorAIRepository.from_fascicoli_db(anchor, structured_db=structured_db)
    try:
        from web.services.document_crypto import decrypt_doc, encrypt_doc
    except Exception:
        decrypt_doc = None
        encrypt_doc = None
    central_audit = None
    if has_app_context():
        core_runtime = current_app.extensions.get("core_runtime", {}) or {}
        candidate = core_runtime.get("audit")
        central_audit = candidate if callable(candidate) else None
    return EditorAIService(
        repository,
        get_fascicoli(),
        build_template_repository(),
        build_document_ai_service(),
        central_audit=central_audit,
        encrypt_document=encrypt_doc,
        decrypt_document=decrypt_doc,
    )


__all__ = [
    "build_editor_ai_service",
    "build_template_repository",
    "editor_ai_fascicoli_db_path",
    "editor_ai_tenant_id",
    "editor_ai_user_context",
]
