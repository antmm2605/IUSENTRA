from __future__ import annotations

from dataclasses import asdict

from lex.research import LexResearchService

from .cache import get_retrieval_cache
from .citations import build_citations
from .context_builder import RetrievalContextBuilder
from .dedup import deduplicate_evidence
from .filters import RetrievalFilters
from .query_planner import QueryPlanner
from .ranker import rank_evidence
from .source_router import SourceRouter
from .sources import row_to_evidence


class RetrievalOrchestrator:
    def __init__(
        self,
        *,
        query_planner=None,
        source_router=None,
        filters=None,
        research_service: LexResearchService | None = None,
        context_builder: RetrievalContextBuilder | None = None,
        retrieval_cache=None,
    ) -> None:
        self.query_planner = query_planner or QueryPlanner()
        self.source_router = source_router or SourceRouter()
        self.filters = filters or RetrievalFilters()
        self.research_service = research_service or LexResearchService()
        self.context_builder = context_builder or RetrievalContextBuilder()
        self.retrieval_cache = retrieval_cache or get_retrieval_cache()

    def _is_official_web_source(self, source) -> bool:
        return source.__class__.__name__ == "OfficialWebSource"

    def _search_sources(self, sources, *, queries, request, context):
        results = []
        used = []
        for source in sources:
            try:
                found = list(source.search(queries=queries, request=request, context=context) or [])
            except Exception:
                continue
            if found:
                results.extend(found)
                used.append(source.__class__.__name__)
        return results, used

    def _studio_context_seed_results(self, context, workflow: str):
        studio = dict((context or {}).get("studio") or {})
        rows = list(studio.get("sources") or [])
        if not rows:
            return []

        default_source_type = {
            "economico": "preventivo",
            "cabina": "strumento",
            "next_action": "agenda",
            "fascicolo": "fascicolo",
            "udienza": "agenda",
            "telematico_status": "telematico",
            "compliance": "compliance",
        }.get(workflow, "legal_intelligence")
        default_score = 0.82 if workflow in {"economico", "cabina", "next_action"} else 0.68

        seeded = []
        for row in rows[:6]:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or row.get("citation") or "").strip()
            excerpt = str(row.get("text") or row.get("excerpt") or row.get("content") or "").strip()
            if not title and not excerpt:
                continue
            payload = dict(row)
            payload.setdefault("type", default_source_type)
            payload.setdefault("id", str(row.get("id") or title.lower().replace(" ", "-")))
            payload.setdefault("title", title or "Contesto studio")
            payload.setdefault("excerpt", excerpt or title)
            payload.setdefault("score", default_score)
            payload.setdefault("authority", "studio_context")
            payload.setdefault("source_level", 3)
            payload.setdefault("trust_class", "B" if workflow in {"economico", "cabina", "next_action"} else "")
            payload["from_studio_context"] = True
            seeded.append(row_to_evidence(payload, default_source_type))
        return seeded

    def _evidence_is_sufficient(self, results, workflow: str) -> bool:
        if not results:
            return False

        top = list(results[:5])
        official_count = 0
        strong_count = 0
        for item in top:
            trust_class = str(getattr(item, "trust_class", "") or (item.get("trust_class") if isinstance(item, dict) else "")).upper()
            source_level = int(getattr(item, "source_level", 0) or (item.get("source_level") if isinstance(item, dict) else 0) or 0)
            score = float(getattr(item, "score", 0.0) or (item.get("score") if isinstance(item, dict) else 0.0) or 0.0)
            if trust_class in {"A", "B"} or source_level <= 2:
                official_count += 1
            if score >= 0.55:
                strong_count += 1

        if workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}:
            return official_count >= 1 and strong_count >= 2
        if workflow in {"fascicolo", "udienza", "telematico_status", "documento"}:
            return strong_count >= 2
        return strong_count >= 1

    def _selection_limit(self, workflow: str) -> int:
        if workflow in {"fascicolo", "udienza", "documento", "telematico_status", "compliance"}:
            return 48
        if workflow in {"cabina", "next_action"}:
            return 24
        return 12

    def collect(self, request, context, workflow: str):
        cache_disabled = bool((getattr(request, "metadata", {}) or {}).get("disable_retrieval_cache"))
        cache_key = self.retrieval_cache.build_key(request, context, workflow)
        if not cache_disabled:
            cached_payload = self.retrieval_cache.get(cache_key)
            if cached_payload is not None:
                evidence_pack = dict(cached_payload.get("evidence_pack") or {})
                metadata = dict(evidence_pack.get("metadata") or {})
                metadata["retrieval_cache_hit"] = True
                metadata["retrieval_cache_ttl_seconds"] = self.retrieval_cache.ttl_seconds
                evidence_pack["metadata"] = metadata
                cached_payload["evidence_pack"] = evidence_pack
                cached_payload["cache"] = {
                    "hit": True,
                    "ttl_seconds": self.retrieval_cache.ttl_seconds,
                }
                return cached_payload

        queries = self.query_planner.plan(request, context, workflow)
        sources = self.source_router.resolve(request, context, workflow)
        studio_seed_results = self._studio_context_seed_results(context, workflow)

        internal_sources = [source for source in sources if not self._is_official_web_source(source)]
        external_sources = [source for source in sources if self._is_official_web_source(source)]

        internal_results, internal_used = self._search_sources(
            internal_sources,
            queries=queries,
            request=request,
            context=context,
        )
        if studio_seed_results:
            internal_results = [*studio_seed_results, *internal_results]
            internal_used = ["StudioContext", *internal_used]
        internal_results = self.filters.apply(internal_results, request, context, workflow)
        internal_results = deduplicate_evidence(internal_results)
        internal_results = rank_evidence(internal_results, request, workflow)

        fallback_triggered = False
        results = list(internal_results)
        used_sources = list(internal_used)

        if (
            not self._evidence_is_sufficient(results, workflow)
            and bool(getattr(request, "allow_external_research", True))
            and external_sources
        ):
            fallback_triggered = True
            external_results, external_used = self._search_sources(
                external_sources,
                queries=queries,
                request=request,
                context=context,
            )
            results.extend(external_results)
            used_sources.extend(external_used)

        results = self.filters.apply(results, request, context, workflow)
        results = deduplicate_evidence(results)
        results = rank_evidence(results, request, workflow)

        selected = results[: self._selection_limit(workflow)]
        citations = build_citations(selected)
        evidence_pack_obj = self.research_service.build_evidence_pack(
            request,
            context,
            workflow,
            queries,
            selected,
            citations,
        )
        retrieval_context = self.context_builder.build(request, context, workflow, queries, sources)
        sufficient = bool(getattr(evidence_pack_obj, "sufficient", False))
        evidence_pack = asdict(evidence_pack_obj)
        metadata = dict(evidence_pack.get("metadata") or {})
        metadata["retrieval_cache_hit"] = False
        metadata["retrieval_cache_ttl_seconds"] = self.retrieval_cache.ttl_seconds
        request_metadata = dict(getattr(request, "metadata", {}) or {})
        external_sources_used = bool(
            "OfficialWebSource" in used_sources
            or any(str(getattr(item, "source_type", "")).lower() == "web_ufficiale" for item in selected)
        )
        metadata["fascicolo_first"] = bool(request_metadata.get("fascicolo_first"))
        metadata["external_sources_used"] = external_sources_used
        metadata["external_sources_reason"] = request_metadata.get("external_sources_reason") or None
        evidence_pack["metadata"] = metadata
        payload = {
            "queries": list(evidence_pack_obj.queries or queries),
            "items": selected,
            "citations": list(evidence_pack_obj.citations or citations),
            "evidence_pack": evidence_pack,
            "official_sources": list(evidence_pack_obj.official_sources or []),
            "trusted_sources": list(evidence_pack_obj.trusted_sources or []),
            "retrieval_context": retrieval_context,
            "source_comparison": list(getattr(evidence_pack_obj, "compared_sources", []) or []),
            "coverage_gaps": list(getattr(evidence_pack_obj, "coverage_gaps", []) or []),
            "conflicting_items": list(getattr(evidence_pack_obj, "conflicting_items", []) or []),
            "fallback_triggered": fallback_triggered,
            "fascicolo_first": bool(request_metadata.get("fascicolo_first")),
            "external_sources_used": external_sources_used,
            "external_sources_reason": request_metadata.get("external_sources_reason") or None,
            "evidence_sufficient": sufficient,
            "used_sources": used_sources,
            "cache": {
                "hit": False,
                "ttl_seconds": self.retrieval_cache.ttl_seconds,
            },
        }
        if not cache_disabled:
            self.retrieval_cache.set(cache_key, payload)
        return payload
