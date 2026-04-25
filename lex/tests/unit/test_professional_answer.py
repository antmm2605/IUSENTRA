from __future__ import annotations

from lex.contracts import Citation, EvidenceItem, GuardVerdict, LexRequest, ProviderDraft
from lex.formatting.answer_builder import AnswerBuilder


def _request(query: str, *, fascicolo_id: str | None = None) -> LexRequest:
    return LexRequest(
        tenant_id="tenant-professional",
        user_id="utente-test",
        session_id="sessione-test",
        query=query,
        fascicolo_id=fascicolo_id,
    )


def test_risposta_fascicolo_viene_strutturata_con_qualita_e_azioni():
    response = AnswerBuilder().build_response(
        request=_request("riepiloga il fascicolo", fascicolo_id="FAS-1"),
        context={"structured_context": {"fascicolo": {"numero": "1025/2024"}}},
        workflow="fascicolo",
        evidence={
            "items": [
                EvidenceItem(
                    source_type="fascicolo",
                    source_id="FAS-1",
                    title="RG 1025/2024",
                    content="Documenti e udienze censiti.",
                    score=0.91,
                )
            ],
            "citations": [
                Citation(
                    source_type="fascicolo",
                    source_id="FAS-1",
                    title="RG 1025/2024",
                    excerpt="Documenti e udienze censiti.",
                    confidence=0.91,
                )
            ],
            "evidence_pack": {
                "trusted_sources": ["RG 1025/2024"],
                "coverage_gaps": [],
                "sufficient": True,
            },
            "trusted_sources": ["RG 1025/2024"],
            "evidence_sufficient": True,
        },
        draft=ProviderDraft(text="Il fascicolo risulta completo sul piano documentale."),
        verdict=GuardVerdict(allowed=True, risk_level="low"),
    )

    assert "**Sintesi operativa**" in response.answer
    assert "**Quadro verificato**" in response.answer
    assert "**Qualita della risposta**" in response.answer
    assert "Fascicolo considerato: 1025/2024" in response.answer
    assert "Apri il fascicolo" in " ".join(response.next_actions)
    assert response.metadata["professional_answer"]["enabled"] is True
    assert response.metadata["professional_answer"]["human_review_required"] is False


def test_risposta_normativa_incompleta_richiede_revisione_professionale():
    response = AnswerBuilder().build_response(
        request=_request("qual e la norma applicabile"),
        context={},
        workflow="normativa",
        evidence={
            "items": [
                EvidenceItem(
                    source_type="normativa",
                    source_id="norm-raw",
                    title="Richiamo non verificato",
                    content="Riferimento non sufficiente.",
                    score=0.52,
                )
            ],
            "citations": [],
            "evidence_pack": {
                "official_sources": [],
                "trusted_sources": [],
                "coverage_gaps": ["Manca una fonte ufficiale verificata."],
                "sufficient": False,
            },
            "coverage_gaps": ["Manca una fonte ufficiale verificata."],
            "evidence_sufficient": False,
        },
        draft=ProviderDraft(text="Non posso chiudere il parere senza fonte ufficiale."),
        verdict=GuardVerdict(allowed=True, risk_level="high"),
    )

    assert "**Risposta professionale**" in response.answer
    assert "**Limiti e verifiche**" in response.answer
    assert "Manca una fonte ufficiale verificata." in response.answer
    assert "Revisione professionale richiesta" in response.answer
    assert response.metadata["professional_answer"]["human_review_required"] is True
    assert response.warnings == [
        "Risposta da revisionare: rischio elevato o fonti non ancora complete."
    ]
