from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest
from lex.retrieval.orchestrator import RetrievalOrchestrator


class StaticPlanner:
    def plan(self, request, context, workflow):
        return [request.query, "riferimenti ufficiali aggiornati"]


class PassFilters:
    def apply(self, results, request, context, workflow):
        return list(results)


class OfficialSource:
    source_name = "official_web"

    def search(self, queries, request, context):
        return [
            EvidenceItem(
                source_type="web_ufficiale",
                source_id="off-1",
                title="Ministero della Giustizia",
                content="Fonte ufficiale disponibile",
                score=0.95,
                metadata={"url": "https://www.giustizia.it/it/fonte", "authority": "official"},
            )
        ]


class NormativeSource:
    source_name = "normative"

    def search(self, queries, request, context):
        return [
            EvidenceItem(
                source_type="normativa",
                source_id="norma-1",
                title="Normattiva",
                content="Testo consolidato disponibile",
                score=0.84,
                metadata={"url": "https://www.normattiva.it/atto", "authority": "institutional"},
            )
        ]


class StaticRouter:
    def resolve(self, request, context, workflow):
        return [OfficialSource(), NormativeSource()]


def test_retrieval_orchestrator_builds_evidence_pack_with_official_and_trusted_sources():
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

    payload = orchestrator.collect(request, {"studio": {"effective_question": request.query}}, "chat")

    assert payload["official_sources"] == ["Ministero della Giustizia", "Normattiva"]
    assert "Normattiva" in payload["trusted_sources"]
    assert payload["retrieval_context"]["official_web_requested"] is True
    assert payload["evidence_pack"]["metadata"]["workflow"] == "chat"