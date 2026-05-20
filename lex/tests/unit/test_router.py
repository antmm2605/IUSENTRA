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
    assert workflow == "telematico_status"


def test_router_resolves_atto_workflow():
    workflow = LexRouter().resolve_workflow(_request("draft_act_support"))
    assert workflow == "atto"


def test_router_resolves_template_act_workflow_from_query():
    request = _request("ask_lex")
    request.query = "crea atto di citazione per Rossi"

    workflow = LexRouter().resolve_workflow(request)

    assert workflow == "atto_da_template"


def test_router_keeps_pec_lookup_out_of_drafting():
    request = _request("ask_lex")
    request.query = "ultima PEC ricevuta"

    workflow = LexRouter().resolve_workflow(request)

    assert workflow == "cabina"


def test_router_defaults_to_chat():
    workflow = LexRouter().resolve_workflow(_request("ask_lex"))
    assert workflow == "question_answering"


def test_router_infers_normativa_from_query_text():
    request = _request("ask_lex")
    request.query = "Qual e la normativa vigente sul deposito telematico?"

    workflow = LexRouter().resolve_workflow(request)

    assert workflow == "normativa"


def test_router_infers_economico_from_query_text():
    request = _request("ask_lex")
    request.query = "Calcola il preventivo e la parcella della pratica"

    workflow = LexRouter().resolve_workflow(request)

    assert workflow == "economico"
