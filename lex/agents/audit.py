"""Audit redatto per run, approvazioni e scritture agentiche."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from flask import current_app, has_app_context

from .models import utc_now_iso
from .serialization import redact_for_audit


def audit_hash(payload: Any) -> str:
    raw = json.dumps(redact_for_audit(payload), ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def record_agent_audit(event: str, *, actor: str = "", run_id: str = "", details: Any | None = None) -> str:
    redacted = {
        "event": event,
        "actor": actor,
        "run_id": run_id,
        "at": utc_now_iso(),
        "details": redact_for_audit(details or {}),
    }
    digest = audit_hash(redacted)
    if has_app_context():
        try:
            current_app.logger.info("lex_workflow_agent_audit event=%s run=%s hash=%s", event, run_id, digest)
        except Exception:
            pass
    return digest
