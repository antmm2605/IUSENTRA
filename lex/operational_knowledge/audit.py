"""Audit helpers for Lex operational knowledge."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .models import OperationalQueryContext, OperationalRoute
from .serializers import clean_spaces
from .settings import OperationalKnowledgeSettings


class OperationalAuditRecorder:
    def __init__(self, *, settings: OperationalKnowledgeSettings | None = None, sink: list[dict[str, Any]] | None = None) -> None:
        self.settings = settings or OperationalKnowledgeSettings()
        self.sink = sink

    def record(
        self,
        *,
        context: OperationalQueryContext,
        question: str,
        route: OperationalRoute | None,
        sources: list[str],
        objects: list[dict[str, str]],
        outcome: str,
        blocked_reason: str = "",
    ) -> str:
        payload = {
            "tenant": context.tenant_id,
            "user": context.user_id,
            "question": clean_spaces(question)[:500],
            "question_sha256": hashlib.sha256(clean_spaces(question).encode("utf-8")).hexdigest(),
            "route": route.route_id if route else "",
            "intent": route.intent if route else "",
            "sources": list(dict.fromkeys(sources)),
            "objects": objects[:50],
            "outcome": outcome,
            "blocked_reason": blocked_reason,
        }
        if self.sink is not None:
            self.sink.append(payload)
            return f"memory:{len(self.sink)}"
        if not self.settings.audit_enabled:
            return ""

        try:
            from flask import request
            from web.helpers import get_utenti

            manager = get_utenti()
            event = manager.registra_evento(
                "lex.operational.query" if outcome == "ok" else "lex.operational.blocked",
                id_utente=context.user_id,
                username=context.username,
                risorsa_tipo="lex_operational_knowledge",
                risorsa_id=route.route_id if route else "",
                dettagli=json.dumps(payload, ensure_ascii=False, sort_keys=True)[:4000],
                ip=getattr(request, "remote_addr", "") or "",
                esito="OK" if outcome == "ok" else "NEGATO",
            )
            return str(getattr(event, "id", "") or "")
        except Exception:
            return ""
