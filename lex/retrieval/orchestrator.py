"""Orchestrazione del retrieval applicativo di Lex."""

from __future__ import annotations

from .citations import build_citations
from .dedup import deduplicate_evidence
from .filters import RetrievalFilters
from .query_planner import QueryPlanner
from .ranker import rank_evidence
from .source_router import SourceRouter


class RetrievalOrchestrator:
    def __init__(self) -> None:
        self.query_planner = QueryPlanner()
        self.source_router = SourceRouter()
        self.filters = RetrievalFilters()

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
        return {
            "queries": queries,
            "items": selected,
            "citations": build_citations(selected),
        }
