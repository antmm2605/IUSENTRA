from __future__ import annotations

from dataclasses import asdict

from lex.research import LexResearchService

from .citations import build_citations
from .context_builder import RetrievalContextBuilder
from .dedup import deduplicate_evidence
from .filters import RetrievalFilters
from .query_planner import QueryPlanner
from .ranker import rank_evidence
from .source_router import SourceRouter


class RetrievalOrchestrator:
    def __init__(
        self,
        *,
        query_planner=None,
        source_router=None,
        filters=None,
        research_service: LexResearchService | None = None,
        context_builder: RetrievalContextBuilder | None = None,
    ) -> None:
        self.query_planner = query_planner or QueryPlanner()
        self.source_router = source_router or SourceRouter()
        self.filters = filters or RetrievalFilters()
        self.research_service = research_service or LexResearchService()
        self.context_builder = context_builder or RetrievalContextBuilder()

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

    def collect(self, request, context, workflow: str):
        queries = self.query_planner.plan(request, context, workflow)
        sources = self.source_router.resolve(request, context, workflow)

        internal_sources = [source for source in sources if not self._is_official_web_source(source)]
        external_sources = [source for source in sources if self._is_official_web_source(source)]

        internal_results, internal_used = self._search_sources(
            internal_sources,
            queries=queries,
            request=request,
            context=context,
        )
        internal_results = self.filters.apply(internal_results, request, context, workflow)
        internal_results = deduplicate_evidence(internal_results)
        internal_results = rank_evidence(internal_results, request, workflow)

        fallback_triggered = False
        results = list(internal_results)
        used_sources = list(internal_used)

        if not self._evidence_is_sufficient(results, workflow) and bool(getattr(request, "allow_external_research", True)):
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

        selected = results[:12]
        citations = build_citations(selected)
        evidence_pack = self.research_service.build_evidence_pack(
            request,
            context,
            workflow,
            queries,
            selected,
            citations,
        )
        retrieval_context = self.context_builder.build(request, context, workflow, queries, sources)
        sufficient = bool(getattr(evidence_pack, "sufficient", False))
        return {
            "queries": list(evidence_pack.queries or queries),
            "items": selected,
            "citations": list(evidence_pack.citations or citations),
            "evidence_pack": asdict(evidence_pack),
            "official_sources": list(evidence_pack.official_sources or []),
            "trusted_sources": list(evidence_pack.trusted_sources or []),
            "retrieval_context": retrieval_context,
            "source_comparison": list(getattr(evidence_pack, "compared_sources", []) or []),
            "coverage_gaps": list(getattr(evidence_pack, "coverage_gaps", []) or []),
            "conflicting_items": list(getattr(evidence_pack, "conflicting_items", []) or []),
            "fallback_triggered": fallback_triggered,
            "evidence_sufficient": sufficient,
            "used_sources": used_sources,
        }