"""Servizio centrale di Lex Research."""

from __future__ import annotations

from .citation_builder import ResearchCitationBuilder
from .classifier import ResearchClassifier
from .deduplicator import ResearchDeduplicator
from .evidence_pack import EvidencePackBuilder
from .extractor import ResearchExtractor
from .fetcher import ResearchFetcher
from .freshness import FreshnessAnalyzer
from .official_sources import OfficialSourcesCatalog
from .query_planner import ResearchQueryPlanner
from .trusted_sources import TrustedSourcesCatalog


class LexResearchService:
    def __init__(self) -> None:
        self.query_planner = ResearchQueryPlanner()
        self.fetcher = ResearchFetcher()
        self.extractor = ResearchExtractor()
        self.classifier = ResearchClassifier()
        self.deduplicator = ResearchDeduplicator()
        self.citation_builder = ResearchCitationBuilder()
        self.official_sources = OfficialSourcesCatalog()
        self.trusted_sources = TrustedSourcesCatalog()
        self.freshness = FreshnessAnalyzer()
        self.evidence_pack_builder = EvidencePackBuilder()

    def build_evidence_pack(self, request, context, workflow: str, queries, items, citations):
        normalized_queries = self.query_planner.build(request, context, workflow, queries)
        fetched = self.fetcher.collect(items)
        rows = self.extractor.to_rows(fetched)
        classified = self.classifier.classify(rows)
        unique_rows = self.deduplicator.deduplicate(classified)
        citations_list = self.citation_builder.build(unique_rows, citations)
        official_sources = self.official_sources.extract(unique_rows, citations_list)
        trusted_sources = self.trusted_sources.extract(unique_rows, citations_list)
        freshness = self.freshness.measure(unique_rows)
        return self.evidence_pack_builder.build(
            queries=normalized_queries,
            items=items,
            citations=citations_list,
            official_sources=official_sources,
            trusted_sources=trusted_sources,
            freshness=freshness,
            metadata={
                "workflow": workflow,
                "rows_count": len(unique_rows),
            },
        )