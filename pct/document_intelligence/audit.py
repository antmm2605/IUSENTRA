"""Audit adapter per Documenti AI Fascicolo."""

from __future__ import annotations

from typing import Any

from .models import new_id, utc_now
from .security import user_id_from_context


DOCUMENT_AI_AUDIT_EVENTS = {
    "document_ai.upload.started",
    "document_ai.upload.completed",
    "document_ai.upload.failed",
    "document_ai.extraction.completed",
    "document_ai.extraction.failed",
    "document_ai.read",
    "document_ai.search",
    "document_ai.permission_denied",
    "document_ai.version.created",
}


def record_document_ai_event(
    repository: Any,
    event_type: str,
    *,
    tenant_id: str,
    fascicolo_id: str,
    user_context: object,
    document_id: str | None = None,
    version_id: str | None = None,
    sha256: str | None = None,
    filename: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "id": new_id("docaiaudit"),
        "tenant_id": tenant_id,
        "fascicolo_id": fascicolo_id,
        "document_id": document_id or "",
        "version_id": version_id or "",
        "user_id": user_id_from_context(user_context),
        "event_type": event_type,
        "timestamp": utc_now(),
        "sha256": sha256 or "",
        "filename": filename or "",
        "status": status or "",
        "error_code": error_code or "",
        "error_message": error_message or "",
        "payload": payload or {},
    }
    repository.append_audit_event(event)
    return event
