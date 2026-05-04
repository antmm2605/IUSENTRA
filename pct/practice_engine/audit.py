"""Funzioni audit leggere per Practice Engine."""

from __future__ import annotations

from typing import Any

from .repository import PracticeEngineRepository


def record_audit(
    repository: PracticeEngineRepository,
    fascicolo_id: str,
    event_type: str,
    *,
    actor: str = "",
    message: str = "",
    reason: str = "",
    payload: dict[str, Any] | None = None,
):
    return repository.audit(
        fascicolo_id,
        event_type,
        actor=actor,
        message=message,
        reason=reason,
        payload=payload or {},
    )
