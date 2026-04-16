"""Orchestrazione del retrieval applicativo di Lex."""

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

    def collect(self, request, context, workflow: str):
        queries = self.query_planner.plan(request, context, workflow)
        sources = self.source_router.resolve(request, context, workflow)

        results = []
        for source in sources:
            try:
                results.extend(source.search(queries=queries, request=request, context=context))
            except Exception:
                continue

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
        return {
            "queries": list(evidence_pack.queries or queries),
            "items": selected,
            "citations": list(evidence_pack.citations or citations),
            "evidence_pack": asdict(evidence_pack),
            "official_sources": list(evidence_pack.official_sources or []),
            "trusted_sources": list(evidence_pack.trusted_sources or []),
            "retrieval_context": retrieval_context,
        }