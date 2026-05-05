"""Audit per Editor AI."""

from __future__ import annotations

from typing import Any, Callable

from .models import new_id, utc_now
from .validators import clean_text, user_id_from_context


EDITOR_AI_EVENTS = {
    "editor_ai.generation.started",
    "editor_ai.generation.completed",
    "editor_ai.generation.failed",
    "editor_ai.version.created",
    "editor_ai.readback.completed",
    "editor_ai.edit.proposed",
    "editor_ai.edit.accepted",
    "editor_ai.edit.rejected",
    "editor_ai.export.requested",
    "editor_ai.permission_denied",
}


def record_editor_ai_event(
    repository: Any,
    event_type: str,
    *,
    tenant_id: str,
    fascicolo_id: str,
    user_context: object,
    atto_ai_id: str | None = None,
    version_id: str | None = None,
    editor_document_id: str | None = None,
    status: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    payload: dict[str, Any] | None = None,
    central_audit: Callable[..., None] | None = None,
) -> dict[str, Any]:
    clean_payload = dict(payload or {})
    for forbidden in ("text", "html", "content", "editor_document_snapshot"):
        clean_payload.pop(forbidden, None)
    event = {
        "id": new_id("auditatto"),
        "tenant_id": tenant_id,
        "fascicolo_id": fascicolo_id,
        "atto_ai_id": clean_text(atto_ai_id),
        "version_id": clean_text(version_id),
        "editor_document_id": clean_text(editor_document_id),
        "user_id": user_id_from_context(user_context),
        "event_type": clean_text(event_type),
        "status": clean_text(status),
        "error_code": clean_text(error_code),
        "error_message": clean_text(error_message)[:500],
        "payload": clean_payload,
        "timestamp": utc_now(),
    }
    appender = getattr(repository, "append_audit_event", None)
    if callable(appender):
        appender(event)
    if callable(central_audit):
        try:
            central_audit(event["event_type"], "fascicolo", fascicolo_id, dettagli=f"atto_ai={atto_ai_id or '-'} status={status or '-'}")
        except TypeError:
            central_audit(event["event_type"])
        except Exception:
            pass
    return event
