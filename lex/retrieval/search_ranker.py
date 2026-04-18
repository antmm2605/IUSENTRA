"""Ranking composito delle fonti per Lex."""

from __future__ import annotations

from typing import Any

from lex.research import classify_request
from lex.research.source_policy import evaluate_source_row

from .documenti import search_document_sources
from .fascicoli import search_fascicolo_sources
from .giurisprudenza import search_giurisprudenza_sources
from .normativa import search_normativa_sources
from .pst import search_pst_sources


class LexSearchRanker:
    def _safe_collect(self, builder, *args):
        try:
            return list(builder(*args) or [])
        except Exception:
            return []

    def collect_and_rank(
        self,
        *,
        pratica_id: str,
        message: str,
        context: dict[str, Any],
        mode: str = "general",
    ) -> list[dict[str, Any]]:
        request_profile = classify_request(message, requested_mode=mode)
        results = []
        results.extend(self._safe_collect(search_fascicolo_sources, pratica_id, message, context))
        results.extend(self._safe_collect(search_document_sources, pratica_id, message, context))
        results.extend(self._safe_collect(search_normativa_sources, message))
        results.extend(self._safe_collect(search_giurisprudenza_sources, message))
        results.extend(self._safe_collect(search_pst_sources, message))
        results.sort(key=lambda row: row.score, reverse=True)
        evaluated = [
            evaluate_source_row(
                row.to_dict(),
                area=request_profile.area,
                mode=request_profile.source_mode,
            )
            for row in results[:12]
        ]
        evaluated.sort(
            key=lambda row: (
                float(row.get("source_policy_score") or 0.0),
                float(row.get("score") or 0.0),
                1 if row.get("verified_reference") else 0,
            ),
            reverse=True,
        )
        return evaluated
