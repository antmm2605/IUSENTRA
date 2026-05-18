from types import SimpleNamespace

from lex.contracts import GuardVerdict, LexRequest
from lex.formatting.answer_builder import AnswerBuilder
from lex.guards.italian_response_guard import (
    detect_non_italian_response,
    rewrite_or_reject_non_italian_response,
)
from lex.prompts.prompt_builder import build_assistente_prompt


def test_guard_rileva_risposta_inglese():
    assert detect_non_italian_response("Okay, here's a breakdown.\n\n**Case Summary**")
    assert detect_non_italian_response("Okay, let's break down this document and extract the key information.")


def test_guard_accetta_risposta_italiana():
    assert not detect_non_italian_response("**Sintesi del fascicolo**\nIl punto rilevante e' documentale.")


def test_guard_riscrive_intestazioni_inglesi_in_italiano():
    text = "Okay, here's a breakdown.\n\n**Case Summary**\nKey Points\nRelevant Documents"
    rewritten = rewrite_or_reject_non_italian_response(text, {"workflow": "fascicolo"})

    assert "Okay, here's" not in rewritten
    assert "Case Summary" not in rewritten
    assert "Key Points" not in rewritten
    assert "Relevant Documents" not in rewritten
    assert "Sintesi del fascicolo" in rewritten
    assert "Punti rilevanti" in rewritten
    assert "Documenti considerati" in rewritten


def test_guard_blocca_formula_inglese_mista_a_sezioni_italiane():
    text = (
        "Sintesi operativa Okay, let's break down this document and extract the key information. "
        "This is a collection of legal documents.\n\nQuadro verificato\nFonti interne verificate: documento."
    )
    rewritten = rewrite_or_reject_non_italian_response(text, {"workflow": "atto"})

    assert "Okay, let's" not in rewritten
    assert "This is a collection" not in rewritten
    assert "Lex deve rispondere sempre in italiano" in rewritten


def test_guard_web_libero_non_usa_fallback_fascicolo():
    text = (
        "Okay, let's break down this document and extract the key information. "
        "This is a collection of legal documents."
    )
    rewritten = rewrite_or_reject_non_italian_response(
        text,
        {"workflow": "fascicolo", "free_web": {"enabled": True}},
    )

    assert "Riformulo sul fascicolo" not in rewritten
    assert "Lex deve rispondere sempre in italiano" in rewritten


def test_guard_fallback_fascicolo_usa_accenti_utf8():
    text = (
        "Okay, let's break down this document and extract the key information. "
        "This is a collection of legal documents."
    )
    rewritten = rewrite_or_reject_non_italian_response(text, {"workflow": "fascicolo"})

    assert "corretta è" in rewritten
    assert "corretta e'" not in rewritten


def test_prompt_impone_italiano_senza_formule_inglesi():
    prompt = build_assistente_prompt(question="riassumi il fascicolo", fascicolo_id="")

    assert "Rispondi sempre e solo in lingua italiana." in prompt
    assert "Case Summary" in prompt
    assert "Sintesi del fascicolo" in prompt


def test_answer_builder_non_restituisce_intestazioni_inglesi():
    request = LexRequest(
        tenant_id="tenant-a",
        user_id="user-1",
        session_id="s-1",
        query="riassumi il fascicolo",
        fascicolo_id="fas-1",
        metadata={"fascicolo_first": True},
    )
    draft = SimpleNamespace(text="Okay, here's a breakdown.\n\n**Case Summary**\nKey Points", metadata={})
    response = AnswerBuilder().build_response(
        request=request,
        context={},
        workflow="fascicolo",
        evidence={"items": [], "evidence_pack": {"metadata": {}}, "evidence_sufficient": False},
        draft=draft,
        verdict=GuardVerdict(allowed=True),
    )

    assert "Okay, here's" not in response.answer
    assert "Case Summary" not in response.answer
    assert "Key Points" not in response.answer
    assert "Sintesi del fascicolo" in response.answer
    assert response.metadata["italian_response_guard_applied"] is True
