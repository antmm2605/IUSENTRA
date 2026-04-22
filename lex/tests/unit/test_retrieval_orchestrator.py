from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest
from lex.retrieval.cache import clear_retrieval_cache
from lex.retrieval.orchestrator import RetrievalOrchestrator
from lex.retrieval.sources.official_web import OfficialWebSource as RealOfficialWebSource


class StaticPlanner:
    def plan(self, request, context, workflow):
        return [request.query, "riferimenti ufficiali aggiornati"]


class PassFilters:
    def apply(self, results, request, context, workflow):
        return list(results)


class OfficialWebSource:
    source_name = "official_web"

    def __init__(self) -> None:
        self.calls = 0

    def search(self, queries, request, context):
        self.calls += 1
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

    def __init__(self) -> None:
        self.calls = 0

    def search(self, queries, request, context):
        self.calls += 1
        return []


class StaticRouter:
    def __init__(self) -> None:
        self.internal = EmptyNormativeSource()
        self.official = OfficialWebSource()

    def resolve(self, request, context, workflow):
        return [self.internal, self.official]


class RestrictedRegistryRouter:
    def __init__(self) -> None:
        self.internal = EmptyNormativeSource()
        self.official = RealOfficialWebSource(request_get=lambda *args, **kwargs: _EmptyResponse())

    def resolve(self, request, context, workflow):
        return [self.internal, self.official]


class _EmptyResponse:
    status_code = 200
    text = "<html><body></body></html>"


def test_retrieval_orchestrator_triggers_official_fallback_and_builds_comparison():
    clear_retrieval_cache()
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
    assert payload["cache"]["hit"] is False


def test_retrieval_orchestrator_riusa_cache_tenant_aware_sulla_stessa_richiesta():
    clear_retrieval_cache()
    router = StaticRouter()
    orchestrator = RetrievalOrchestrator(
        query_planner=StaticPlanner(),
        source_router=router,
        filters=PassFilters(),
    )
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="aggiorna le fonti ufficiali sul tema",
    )

    first = orchestrator.collect(request, {"studio": {"effective_question": request.query}}, "normativa")
    second = orchestrator.collect(request, {"studio": {"effective_question": request.query}}, "normativa")

    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert router.internal.calls == 1
    assert router.official.calls == 1


def test_retrieval_orchestrator_non_condivide_cache_tra_tenant_diversi():
    clear_retrieval_cache()
    router = StaticRouter()
    orchestrator = RetrievalOrchestrator(
        query_planner=StaticPlanner(),
        source_router=router,
        filters=PassFilters(),
    )
    first_request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="aggiorna le fonti ufficiali sul tema",
    )
    second_request = LexRequest(
        tenant_id="tenant-2",
        user_id="user-1",
        session_id="session-1",
        query="aggiorna le fonti ufficiali sul tema",
    )

    orchestrator.collect(first_request, {"studio": {"effective_question": first_request.query}}, "normativa")
    second = orchestrator.collect(second_request, {"studio": {"effective_question": second_request.query}}, "normativa")

    assert second["cache"]["hit"] is False
    assert router.internal.calls == 2
    assert router.official.calls == 2


def test_retrieval_orchestrator_espone_gap_su_fonti_partner_non_cercabili_via_web_pubblico():
    clear_retrieval_cache()
    orchestrator = RetrievalOrchestrator(
        query_planner=StaticPlanner(),
        source_router=RestrictedRegistryRouter(),
        filters=PassFilters(),
    )
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="Mi serve una visura dal registro imprese",
        metadata={"source_ids": ["registro_imprese_api"]},
    )

    payload = orchestrator.collect(request, {"studio": {"effective_question": request.query}}, "normativa")

    assert payload["fallback_triggered"] is True
    assert any("fonti partner" in gap.lower() for gap in payload["coverage_gaps"])
    assert payload["evidence_pack"]["metadata"]["source_registry_partner"][0]["key"] == "registro_imprese_api"
