"""Builder strutturato del contesto Lex."""

from __future__ import annotations

from typing import Any

from lex.guards.privacy_guard import PrivacyGuard
from .agenda_context import load_agenda_context
from .anagrafica_context import load_anagrafica_context
from .document_context import load_document_context
from .fascicolo_context import load_fascicolo_context
from .fascicolo_sections_context import load_fascicolo_sections_context
from .operational_context import (
    load_economic_context,
    load_fascicolo_compliance_context,
    load_fascicolo_intelligence_context,
    load_studio_operational_context,
)
from .permissions_context import build_permissions_context
from .runtime_context import build_runtime_context
from .scadenze_context import load_scadenze_context
from .session_context import build_session_context
from .studio_context import build_studio_context
from .telematico_context import build_telematico_context
from .user_context import build_user_context


class LexContextBuilder:
    def __init__(self, *, privacy_guard: PrivacyGuard | None = None) -> None:
        self._privacy_guard = privacy_guard or PrivacyGuard()

    @staticmethod
    def _lightweight_context_requested(request) -> bool:
        metadata = dict(getattr(request, "metadata", {}) or {})
        return bool(
            metadata.get("lightweight_context")
            or metadata.get("performance_smoke")
            or metadata.get("benchmark_mode") == "performance_smoke"
        )

    @staticmethod
    def _performance_smoke_requested(request) -> bool:
        metadata = dict(getattr(request, "metadata", {}) or {})
        return bool(metadata.get("performance_smoke") or metadata.get("benchmark_mode") == "performance_smoke")

    @staticmethod
    def _free_web_context_requested(request) -> bool:
        metadata = dict(getattr(request, "metadata", {}) or {})
        profile = dict(metadata.get("request_profile") or {}) if isinstance(metadata.get("request_profile"), dict) else {}
        source_mode = str(profile.get("source_mode") or metadata.get("source_mode") or "").strip().lower()
        if source_mode in {"free", "free_web", "web_libero", "web libero", "ricerca_libera", "ricerca libera", "libera"}:
            return True
        return any(
            metadata.get(key) is True or str(metadata.get(key) or "").strip().lower() in {"1", "true", "vero", "yes", "si", "sì", "on", "enabled", "abilitato", "attivo"}
            for key in ("free_web_enabled", "force_free_web_search", "manual_free_web_enabled", "free_web")
        )

    def _safe_section(self, loader, *, fallback, **kwargs):
        try:
            return loader(**kwargs)
        except Exception:
            return fallback

    def build_request_context(self, request, workflow: str) -> dict[str, Any]:
        pratica_id = str(request.fascicolo_id or "").strip()
        question = str(getattr(request, "query", "") or "").strip()
        if self._performance_smoke_requested(request):
            return {
                "workflow": workflow,
                "studio": {
                    "effective_question": question,
                    "sources": [],
                },
                "utente": {"user_id": str(getattr(request, "user_id", "") or "")},
                "sessione": {"session_id": str(getattr(request, "session_id", "") or "")},
                "runtime": {"performance_smoke": True},
            }
        if self._free_web_context_requested(request):
            return {
                "workflow": workflow,
                "studio": build_studio_context(request),
                "free_web": {
                    "enabled": True,
                    "policy": "solo ricerca web libera della singola richiesta, senza dati studio",
                },
            }
        sanitized = self._privacy_guard.sanitize_sections(
            {
                "workflow": workflow,
                "studio": build_studio_context(request),
                "utente": build_user_context(request),
                "permessi": build_permissions_context(request),
                "sessione": build_session_context(request),
                "runtime": build_runtime_context(request),
                "agenda": self._safe_section(load_agenda_context, fallback=[], pratica_id=pratica_id),
                "scadenziario": self._safe_section(load_scadenze_context, fallback=[], pratica_id=pratica_id),
                "studio_operativo": {}
                if self._lightweight_context_requested(request)
                else self._safe_section(
                    load_studio_operational_context,
                    fallback={},
                    question=question,
                ),
                "economico": {}
                if self._lightweight_context_requested(request)
                else self._safe_section(
                    load_economic_context,
                    fallback={},
                    question=question,
                    pratica_id=pratica_id,
                    fascicolo_id=str(request.fascicolo_id or "").strip(),
                ),
                "telematico": build_telematico_context(request),
            }
        )
        if request.fascicolo_id:
            documenti_context = self._safe_section(
                load_document_context,
                fallback=[],
                pratica_id=pratica_id,
                fascicolo_id=str(request.fascicolo_id or "").strip(),
            )
            sanitized["fascicolo"] = self._safe_section(
                load_fascicolo_context,
                fallback={},
                pratica_id=pratica_id,
                fascicolo_id=str(request.fascicolo_id or "").strip(),
            )
            sanitized["documenti"] = documenti_context
            sanitized["fascicolo_sezioni"] = self._safe_section(
                load_fascicolo_sections_context,
                fallback={},
                pratica_id=pratica_id,
                fascicolo_id=str(request.fascicolo_id or "").strip(),
                documenti=documenti_context,
            )
            sanitized["fascicolo_intelligence"] = self._safe_section(
                load_fascicolo_intelligence_context,
                fallback={},
                pratica_id=pratica_id,
                fascicolo_id=str(request.fascicolo_id or "").strip(),
            )
            sanitized["conformita_fascicolo"] = self._safe_section(
                load_fascicolo_compliance_context,
                fallback={},
                pratica_id=pratica_id,
                fascicolo_id=str(request.fascicolo_id or "").strip(),
            )
            sanitized["anagrafica"] = self._safe_section(
                load_anagrafica_context,
                fallback={"clienti": [], "soggetti": []},
                pratica_id=pratica_id,
            )
        if request.document_id:
            sanitized["documento"] = {"document_id": str(request.document_id)}
        return sanitized

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

        documenti_context = self._safe_section(
            load_document_context,
            fallback=[],
            pratica_id=pratica_id,
            fascicolo_id=fascicolo_id,
        )
        structured_sections = self._privacy_guard.sanitize_sections(
            {
                "fascicolo": self._safe_section(load_fascicolo_context, fallback={}, pratica_id=pratica_id, fascicolo_id=fascicolo_id),
                "documenti": documenti_context,
                "fascicolo_sezioni": self._safe_section(
                    load_fascicolo_sections_context,
                    fallback={},
                    pratica_id=pratica_id,
                    fascicolo_id=fascicolo_id,
                    documenti=documenti_context,
                ),
                "studio_operativo": self._safe_section(
                    load_studio_operational_context,
                    fallback={},
                    question=effective_question,
                ),
                "economico": self._safe_section(
                    load_economic_context,
                    fallback={},
                    question=effective_question,
                    pratica_id=pratica_id,
                    fascicolo_id=fascicolo_id,
                ),
                "fascicolo_intelligence": self._safe_section(
                    load_fascicolo_intelligence_context,
                    fallback={},
                    pratica_id=pratica_id,
                    fascicolo_id=fascicolo_id,
                ),
                "conformita_fascicolo": self._safe_section(
                    load_fascicolo_compliance_context,
                    fallback={},
                    pratica_id=pratica_id,
                    fascicolo_id=fascicolo_id,
                ),
                "agenda": self._safe_section(load_agenda_context, fallback=[], pratica_id=pratica_id),
                "scadenze": self._safe_section(load_scadenze_context, fallback=[], pratica_id=pratica_id),
                "anagrafica": self._safe_section(load_anagrafica_context, fallback={"clienti": [], "soggetti": []}, pratica_id=pratica_id),
                "mode": str(mode or "").strip(),
            }
        )

        payload = dict(studio_context or {})
        payload["structured_context"] = structured_sections
        return payload
