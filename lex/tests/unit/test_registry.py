from __future__ import annotations

from lex.contracts import LexRequest
from lex.registry import build_lex_service


def test_registry_builds_application_service_that_can_answer():
    service = build_lex_service()

    response = service.ask(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="qual e la prossima azione",
        )
    )

    assert response.answer
    assert response.metadata["workflow"] == "chat"
    assert "provider" in response.metadata
    assert "module_packs" in response.metadata
    assert "working_memory" in response.metadata
    assert "evidence_pack" in response.metadata