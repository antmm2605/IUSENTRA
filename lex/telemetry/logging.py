"""Telemetry logging del bounded context Lex."""

from __future__ import annotations

import logging


logger = logging.getLogger("lex")


class LexTelemetry:
    def record(self, request, workflow, context, evidence, response):
        evidence_pack = dict((evidence or {}).get("evidence_pack") or {})
        metadata = dict(getattr(response, "metadata", {}) or {})
        logger.info(
            "LEX request tenant=%s user=%s workflow=%s evidence=%s packs=%s insights=%s official=%s trusted=%s",
            request.tenant_id,
            request.user_id,
            workflow,
            len(list((evidence or {}).get("items") or [])),
            len(list(metadata.get("module_packs") or [])),
            len(list(metadata.get("insights") or [])),
            len(list(evidence_pack.get("official_sources") or [])),
            len(list(evidence_pack.get("trusted_sources") or [])),
        )