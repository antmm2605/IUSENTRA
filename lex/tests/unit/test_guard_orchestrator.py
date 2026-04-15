from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import LexRequest
from lex.guards.orchestrator import GuardOrchestrator


def test_guard_orchestrator_blocks_missing_tenant():
    guards = GuardOrchestrator()
    request = LexRequest(tenant_id="", user_id="user-1", session_id="session-1", query="test")
    context = {"permessi": {"can_use_lex": True}}

    verdict = guards.run_pre(request, context, "chat")

    assert verdict.allowed is False
    assert "Missing tenant_id" in verdict.reasons


def test_guard_orchestrator_warns_on_empty_evidence():
    guards = GuardOrchestrator()
    request = LexRequest(tenant_id="tenant-1", user_id="user-1", session_id="session-1", query="test")
    context = {"permessi": {"can_use_lex": True}}
    draft = SimpleNamespace(text="risposta di test")

    verdict = guards.run_post(request, context, "chat", {"items": []}, draft)

    assert verdict.allowed is True
    assert verdict.warnings
