"""Runtime Flask per l'indicizzazione Lex dei documenti fascicolo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, session

from pct.document_intelligence import DocumentAIRepository, DocumentAIService, LexIndexingSummary
from pct.document_intelligence.sources import DocumentAISource, collect_fascicolo_document_sources
from web.helpers import get_fascicoli
from web.services.storage_runtime import get_request_studio_db, get_request_storage_runtime
from web.services.tenant_paths import tenant_data_path


def fascicoli_db_path() -> str:
    if has_request_context():
        return tenant_data_path(
            "FASCICOLI_DB",
            str(
                current_app.config.get("FASCICOLI_DB")
                or current_app.config.get("FASCICOLI_DB_PATH")
                or Path(current_app.instance_path) / "fascicoli" / "fascicoli.json"
            ),
            require_tenant=bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)),
        )
    if has_app_context():
        return str(
            current_app.config.get("FASCICOLI_DB")
            or current_app.config.get("FASCICOLI_DB_PATH")
            or Path(current_app.instance_path) / "fascicoli" / "fascicoli.json"
        )
    return str(Path("data") / "fascicoli" / "fascicoli.json")


def document_ai_tenant_id() -> str:
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
        profile = get_request_storage_runtime(fascicoli_db_path())
        return profile.tenant_slug or "single-studio"
    return "single-studio"


def document_ai_user_context() -> dict[str, Any]:
    user = g.get("utente_corrente") if has_request_context() else None
    return {
        "user": user,
        "user_id": str(getattr(user, "id", "") or getattr(user, "username", "") or ""),
    }


def build_document_ai_service() -> DocumentAIService:
    anchor = fascicoli_db_path()
    structured_db = get_request_studio_db(anchor) if has_app_context() else None
    repository = DocumentAIRepository.from_fascicoli_db(anchor, structured_db=structured_db)
    max_size = 25 * 1024 * 1024
    if has_app_context():
        max_size = int(current_app.config.get("DOCUMENT_AI_MAX_UPLOAD_BYTES") or max_size)
    return DocumentAIService(repository, get_fascicoli(), max_size_bytes=max_size)


def collect_document_ai_sources_for_fascicolo(
    fascicolo_id: str,
    *,
    tenant_id: str | None = None,
) -> list[DocumentAISource]:
    gestore = get_fascicoli()
    fascicolo = gestore.get(str(fascicolo_id or "").strip())
    if not fascicolo:
        return []
    try:
        from web.services.document_crypto import decrypt_doc
    except Exception:
        decrypt_doc = None
    return collect_fascicolo_document_sources(
        tenant_id=tenant_id or document_ai_tenant_id(),
        fascicolo_id=str(fascicolo_id or "").strip(),
        fascicolo=fascicolo,
        documents_root=getattr(gestore, "documents_dir", Path(".")),
        decrypt=decrypt_doc,
    )


def build_lex_indexing_summary_payload(
    fascicolo_id: str,
    *,
    process: bool = False,
    retry_errors: bool = False,
    user_context: object | None = None,
) -> dict[str, Any]:
    tenant_id = document_ai_tenant_id()
    context = user_context if user_context is not None else document_ai_user_context()
    service = build_document_ai_service()
    sources = collect_document_ai_sources_for_fascicolo(fascicolo_id, tenant_id=tenant_id)
    if process:
        result = service.process_lex_indexing_sources(
            tenant_id,
            fascicolo_id,
            sources,
            context,
            retry_errors=retry_errors,
        )
        return result.summary.to_dict()
    summary: LexIndexingSummary = service.build_lex_indexing_summary(tenant_id, fascicolo_id, sources, context)
    if _lex_summary_needs_automatic_processing(summary, sources):
        result = service.process_lex_indexing_sources(
            tenant_id,
            fascicolo_id,
            sources,
            context,
            retry_errors=True,
        )
        return result.summary.to_dict()
    return summary.to_dict()


def _lex_summary_needs_automatic_processing(summary: LexIndexingSummary, sources: list[DocumentAISource]) -> bool:
    if summary.queued or summary.stale or summary.not_indexed:
        return True
    if not summary.errors:
        return False
    return any(
        source.supported and str(source.filename or "").lower().endswith(".p7m")
        for source in sources
    )


__all__ = [
    "build_document_ai_service",
    "build_lex_indexing_summary_payload",
    "collect_document_ai_sources_for_fascicolo",
    "document_ai_tenant_id",
    "document_ai_user_context",
    "fascicoli_db_path",
]
