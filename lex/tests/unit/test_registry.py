from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import LexRequest
from lex.providers.registry import ProviderRegistry
from lex.registry import build_lex_service


def test_registry_builds_application_service_that_can_answer():
    service = build_lex_service()

    response = service.ask(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="Qual e la prossima azione operativa sul fascicolo?",
            intent="resolve_operational_question",
        )
    )

    assert response.answer
    assert response.metadata["workflow"] == "cabina"
    assert response.metadata["provider"] == "deterministic"
    assert "module_packs" in response.metadata
    assert "working_memory" in response.metadata
    assert "evidence_pack" in response.metadata
    assert "official_sources" in response.metadata
    assert "coverage_gaps" in response.metadata
    assert "fallback_triggered" in response.metadata
    assert "evidence_sufficient" in response.metadata
    assert "confidence" in response.metadata


def test_provider_registry_usa_percorso_guidato_per_fascicolo_con_contesto():
    registry = ProviderRegistry()

    provider = registry.pick(
        SimpleNamespace(metadata={}),
        {
            "structured_context": {
                "fascicolo": {"id": "FAS-1", "numero": "1025/2024"},
            }
        },
        "fascicolo",
        {},
    )

    assert provider.provider_name == "deterministic"
