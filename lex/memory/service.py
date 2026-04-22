from __future__ import annotations

from dataclasses import asdict, is_dataclass

from lex.adapters import LexAdapterRegistry
from lex.insights import LexInsightsService

from .economic_memory import EconomicMemoryStore
from .facts import FactMemoryStore
from .profiles import ProfileStore
from .research_index import ResearchIndexStore
from .store import StateStore
from .timeline import TimelineStore
from .working_memory import WorkingMemoryAssembler


class LexMemoryService:
    def __init__(self, *, adapter_registry: LexAdapterRegistry | None = None, insights_service: LexInsightsService | None = None) -> None:
        self.adapter_registry = adapter_registry or LexAdapterRegistry()
        self.insights_service = insights_service or LexInsightsService()
        self.session_state = StateStore()
        self.case_state = StateStore()
        self.session = self.session_state.entries
        self.case = self.case_state.entries
        self.fact_store = FactMemoryStore()
        self.timeline_store = TimelineStore()
        self.profile_store = ProfileStore()
        self.research_index_store = ResearchIndexStore()
        self.economic_memory_store = EconomicMemoryStore()
        self.working_memory = WorkingMemoryAssembler()

    def _serialize(self, value):
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return {key: self._serialize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._serialize(item) for item in value]
        if isinstance(value, tuple):
            return [self._serialize(item) for item in value]
        return value

    def persist(self, request, workflow, context, evidence, response):
        session_id = str(getattr(request, "session_id", "") or "")
        fascicolo_id = str(getattr(request, "fascicolo_id", "") or "")
        module_packs = self.adapter_registry.build_packs(request, workflow, context, evidence or {})
        all_facts = [fact for pack in module_packs for fact in list(getattr(pack, "facts", []) or [])]
        all_events = [event for pack in module_packs for event in list(getattr(pack, "events", []) or [])]

        response_metadata = dict(getattr(response, "metadata", {}) or {})
        response_confidence = float(getattr(response, "confidence", 0.0) or response_metadata.get("confidence") or 0.0)
        source_summary = list(getattr(response, "considered_sources", []) or response_metadata.get("considered_sources") or [])
        missing_evidence = list(getattr(response, "missing_evidence", []) or response_metadata.get("missing_evidence") or [])

        self.session_state.update(
            session_id,
            {
                "last_query": str(getattr(request, "query", "") or ""),
                "last_answer": str(getattr(response, "answer", "") or ""),
                "workflow": workflow,
                "confidence": response_confidence,
                "considered_sources": source_summary,
                "missing_evidence": missing_evidence,
            },
        )
        if fascicolo_id:
            self.case_state.update(
                fascicolo_id,
                {
                    "last_query": str(getattr(request, "query", "") or ""),
                    "last_answer": str(getattr(response, "answer", "") or ""),
                    "workflow": workflow,
                    "confidence": response_confidence,
                    "considered_sources": source_summary,
                    "missing_evidence": missing_evidence,
                },
            )

        self.fact_store.remember(session_id, fascicolo_id, all_facts)
        self.timeline_store.record(session_id, fascicolo_id, all_events)
        self.profile_store.remember(request, context)

        evidence_pack = dict((evidence or {}).get("evidence_pack") or {})
        self.research_index_store.remember(session_id, fascicolo_id, evidence_pack)

        economic_facts = [
            fact
            for fact in all_facts
            if str(getattr(fact, "module", "") or "") in {"preventivi", "tariffario", "fatture"}
        ]
        self.economic_memory_store.remember(session_id, fascicolo_id, economic_facts)

        snapshot = self.working_memory.build(
            session_facts=self.fact_store.session_facts(session_id),
            case_facts=self.fact_store.case_facts(fascicolo_id),
            timeline=self.timeline_store.case_events(fascicolo_id) or self.timeline_store.session_events(session_id),
            profiles=self.profile_store.snapshot(request),
            economic_facts=self.economic_memory_store.case_facts(fascicolo_id) or self.economic_memory_store.session_facts(session_id),
            research_index=self.research_index_store.case_items(fascicolo_id) or self.research_index_store.session_items(session_id),
            module_packs=module_packs,
        )
        insights = self.insights_service.build(
            request=request,
            workflow=workflow,
            module_packs=module_packs,
            evidence_pack=evidence_pack,
            economic_facts=economic_facts,
        )

        metadata = dict(response_metadata)
        metadata.update(
            {
                "module_packs": self._serialize(module_packs),
                "working_memory": self._serialize(snapshot),
                "insights": self._serialize(insights),
                "evidence_pack": evidence_pack,
                "official_sources": list(evidence_pack.get("official_sources") or []),
                "trusted_sources": list(evidence_pack.get("trusted_sources") or []),
                "facts_count": len(all_facts),
                "events_count": len(all_events),
                "confidence": response_confidence,
                "considered_sources": source_summary,
                "missing_evidence": missing_evidence,
                "workflow_outcome": "grounded" if response_confidence >= 0.7 else "needs_review",
                "fallback_triggered": bool((evidence or {}).get("fallback_triggered")),
                "evidence_sufficient": bool((evidence or {}).get("evidence_sufficient")),
                "coverage_gaps": list((evidence or {}).get("coverage_gaps") or []),
                "retrieval_cache": dict((evidence or {}).get("cache") or {}),
            }
        )
        response.metadata = metadata
