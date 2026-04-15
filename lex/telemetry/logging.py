"""Telemetry logging del bounded context Lex."""

from __future__ import annotations

import logging


logger = logging.getLogger("lex")


class LexTelemetry:
    def record(self, request, workflow, context, evidence, response):
        logger.info(
            "LEX request tenant=%s user=%s workflow=%s evidence=%s",
            request.tenant_id,
            request.user_id,
            workflow,
            len(list((evidence or {}).get("items") or [])),
        )
