from __future__ import annotations

from lex.contracts import LexRequest
from lex.router import LexRouter


def _request(intent: str):
    return LexRequest(
        tenant_id="tenant-1",
        user_id="user-1",
        session_id="session-1",
        query="test",
        intent=intent,
    )


def test_router_resolves_telematico_workflow():
    workflow = LexRouter().resolve_workflow(_request("explain_telematico_error"))
    assert workflow == "telematico"


def test_router_resolves_atto_workflow():
    workflow = LexRouter().resolve_workflow(_request("draft_act_support"))
    assert workflow == "atto"


def test_router_defaults_to_chat():
    workflow = LexRouter().resolve_workflow(_request("ask_lex"))
    assert workflow == "chat"
