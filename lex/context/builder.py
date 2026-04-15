"""Builder strutturato del contesto Lex."""

from __future__ import annotations

from typing import Any

from lex.guards.privacy_guard import PrivacyGuard
from .agenda_context import load_agenda_context
from .anagrafica_context import load_anagrafica_context
from .document_context import load_document_context
from .fascicolo_context import load_fascicolo_context
from .scadenze_context import load_scadenze_context


class LexContextBuilder:
    def __init__(self, *, privacy_guard: PrivacyGuard | None = None) -> None:
        self._privacy_guard = privacy_guard or PrivacyGuard()

    def _safe_section(self, loader, *, fallback, **kwargs):
        try:
            return loader(**kwargs)
        except Exception:
            return fallback

    def build(
        self,
        *,
        question: str,
        mode: str,
        pratica_id: str = "",
        fascicolo_id: str = "",
        history_messages: list[dict[str, object]] | None = None,
        routing,
        build_studio_context,
        build_today_summary,
    ) -> dict[str, Any]:
        effective_question = str(question or "").strip()
        if bool(getattr(routing, "is_daily_overview", False)):
            studio_context = build_today_summary(question=effective_question)
        else:
            studio_context = build_studio_context(
                effective_question,
                mode="chat",
                messages=history_messages or [],
            )

        structured_sections = self._privacy_guard.sanitize_sections(
            {
                "fascicolo": self._safe_section(load_fascicolo_context, fallback={}, pratica_id=pratica_id, fascicolo_id=fascicolo_id),
                "documenti": self._safe_section(load_document_context, fallback=[], pratica_id=pratica_id, fascicolo_id=fascicolo_id),
                "agenda": self._safe_section(load_agenda_context, fallback=[], pratica_id=pratica_id),
                "scadenze": self._safe_section(load_scadenze_context, fallback=[], pratica_id=pratica_id),
                "anagrafica": self._safe_section(load_anagrafica_context, fallback={"clienti": [], "soggetti": []}, pratica_id=pratica_id),
                "mode": str(mode or "").strip(),
            }
        )

        payload = dict(studio_context or {})
        payload["structured_context"] = structured_sections
        return payload
