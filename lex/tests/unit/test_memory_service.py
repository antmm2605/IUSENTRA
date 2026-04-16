from __future__ import annotations

from lex.adapters import LexAdapterRegistry
from lex.contracts import Citation, EvidenceItem, LexRequest, LexResponse
from lex.insights import LexInsightsService
from lex.memory.service import LexMemoryService


def test_memory_service_persists_module_packs_working_memory_and_insights():
    service = LexMemoryService(
        adapter_registry=LexAdapterRegistry(),
        insights_service=LexInsightsService(),
    )
    request = LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="preparami un quadro operativo del fascicolo",
        fascicolo_id="FAS-1",
    )
    context = {
        "studio": {
            "legal_dashboard_headline": {
                "motori_attivi": 9,
                "fonti_aggiornate": 28,
                "alert_aperti": 8,
                "riferimenti_ufficiali": 154,
            },
            "engine_ids": [f"motore-{index}" for index in range(1, 10)],
            "source_ids": ["fonte-1", "fonte-2"],
            "verified_legal_references": [{"id": "rif-1"}],
            "legal_route_scope": "contenzioso civile",
            "research_strategy": "focus_fonti_ufficiali",
        },
        "fascicolo": {
            "id": "FAS-1",
            "stato": "attivo",
            "fase": "istruttoria",
            "ufficio": "Tribunale di Milano",
            "parti": [{"nome": "Mario Rossi"}],
        },
        "documenti": [
            {"id": "DOC-1", "title": "Atto di citazione", "tipo": "atto"},
            {"id": "DOC-2", "title": "Comparsa di risposta", "tipo": "comparsa"},
        ],
    }
    evidence = {
        "queries": ["nullita contratto"],
        "items": [
            EvidenceItem(
                source_type="web_ufficiale",
                source_id="ministero-1",
                title="Ministero della Giustizia",
                content="Comunicato ufficiale",
                score=0.98,
                metadata={"url": "https://www.giustizia.it/it/comunicato", "authority": "official"},
            )
        ],
        "citations": [
            Citation(
                source_type="web_ufficiale",
                source_id="ministero-1",
                title="Ministero della Giustizia",
                excerpt="Comunicato ufficiale",
                confidence=0.98,
                authority="official",
                url="https://www.giustizia.it/it/comunicato",
            )
        ],
        "evidence_pack": {
            "queries": ["nullita contratto"],
            "official_sources": ["Ministero della Giustizia"],
            "trusted_sources": ["Ministero della Giustizia"],
            "freshness": {"dated_items": 0, "latest_date": ""},
        },
    }
    response = LexResponse(answer="Quadro pronto")

    service.persist(request, "fascicolo", context, evidence, response)

    modules = {pack["module"] for pack in response.metadata["module_packs"]}
    assert {"cabina", "fascicoli", "documenti", "ricerca_legale"}.issubset(modules)
    assert response.metadata["working_memory"]["session_facts"]
    assert response.metadata["working_memory"]["timeline"]
    assert response.metadata["official_sources"] == ["Ministero della Giustizia"]
    assert any(item["insight_type"] == "operational" for item in response.metadata["insights"])