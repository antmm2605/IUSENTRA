from __future__ import annotations

from lex.contracts import GuardVerdict, LexRequest, ProviderDraft
from lex.formatting.answer_builder import AnswerBuilder


def test_evidence_insufficiente_produce_needs_review_confidence_non_alta():
    response = AnswerBuilder().build_response(
        request=LexRequest(
            tenant_id="tenant",
            user_id="utente",
            session_id="sess",
            query="Dammi una risposta operativa",
        ),
        context={},
        workflow="question_answering",
        evidence={
            "items": [],
            "citations": [],
            "evidence_pack": {"coverage_gaps": [], "sufficient": False},
            "coverage_gaps": [],
            "evidence_sufficient": False,
        },
        draft=ProviderDraft(text="Non ho elementi sufficienti per chiudere la risposta."),
        verdict=GuardVerdict(allowed=True, risk_level="low"),
    )

    assert response.answer_mode == "needs_review"
    assert response.confidence < 0.8
    assert response.metadata["confidence_label"] in {"bassa", "media"}
    assert response.warnings or response.next_actions
    assert response.evidence_summary["evidence_sufficient"] is False
