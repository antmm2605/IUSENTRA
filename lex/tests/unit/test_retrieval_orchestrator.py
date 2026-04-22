from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest
from lex.retrieval.orchestrator import RetrievalOrchestrator


class StaticPlanner:
    def plan(self, request, context, workflow):
        return [request.query, "riferimenti ufficiali aggiornati"]


class PassFilters:
    def apply(self, results, request, context, workflow):
        return list(results)


class OfficialWebSource:
    source_name = "official_web"

    def search(self, queries, request, context):
        return [
            EvidenceItem(
                source_type="web_ufficiale",
                source_id="off-1",
                title="Ministero della Giustizia",
                content="Fonte ufficiale disponibile",
                score=0.95,
                authority="Ministero della Giustizia",
                official_url="https://www.giustizia.it/it/fonte",
                trust_class="B",
                source_level=2,
                verified_reference=True,
                metadata={"url": "https://www.giustizia.it/it/fonte", "authority": "official"},
            ),
            EvidenceItem(
                source_type="web_ufficiale",
                source_id="off-2",
                title="Normattiva",
                content="Testo consolidato disponibile",
                score=0.93,
                authority="Normattiva",
                official_url="https://www.normattiva.it/atto",
                trust_class="A",
                source_level=1,
                verified_reference=True,
                metadata={"url": "https://www.normattiva.it/atto", "authority": "official"},
            ),
        ]


class EmptyNormativeSource:
    source_name = "normative"

    def search(self, queries, request, context):
        return []


class StaticRouter:
    def resolve(self, request, context, workflow):
        return [EmptyNormativeSource(), OfficialWebSource()]


def test_retrieval_orchestrator_triggers_official_fallback_and_builds_comparison():
    orchestrator = RetrievalOrchestrator(
        query_planner=StaticPlanner(),
        source_router=StaticRouter(),
        filters=PassFilters(),
    )
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="aggiorna le fonti ufficiali sul tema",
    )

    payload = orchestrator.collect(request, {"studio": {"effective_question": request.query}}, "normativa")

    assert sorted(payload["official_sources"]) == ["Ministero della Giustizia", "Normattiva"]
    assert "Normattiva" in payload["trusted_sources"]
    assert payload["retrieval_context"]["official_web_requested"] is True
    assert payload["evidence_pack"]["metadata"]["workflow"] == "normativa"
    assert payload["fallback_triggered"] is True
    assert payload["evidence_sufficient"] is True
    assert len(payload["source_comparison"]) == 2
    assert payload["coverage_gaps"] == []
