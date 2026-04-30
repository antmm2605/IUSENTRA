from __future__ import annotations

from lex.evaluation.metrics import citation_fidelity, exact_match, refusal_correctness, token_f1
from lex.evaluation.runner import EvaluationCase, evaluate_cases


def test_metriche_estrazione_normalizzano_accenti_spazi_e_token():
    assert exact_match("Procèsso   civile", "processo civile")
    assert not exact_match("processo civile", "processo penale")

    assert token_f1("", "") == {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    assert token_f1("processo civile", "") == {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    assert token_f1("ricorso cautelare urgente", "ricorso urgente") == {
        "precision": 1.0,
        "recall": 0.6667,
        "f1": 0.8,
    }


def test_metriche_citation_fidelity_distinguono_claim_supportati_e_non_supportati():
    result = citation_fidelity(
        claims=[
            "La sentenza riguarda misure cautelari personali",
            "",
            "Il contratto e' stato registrato a Milano",
        ],
        evidence_texts=[
            "La Corte esamina le misure cautelari personali e il procedimento penale.",
            "Nessun dato sulla registrazione del contratto.",
        ],
    )

    assert result["supported_count"] == 1
    assert result["claim_count"] == 3
    assert result["precision"] == 0.3333
    assert result["supported"][0]["support_score"] >= 0.35
    assert "" in result["unsupported"]
    assert "Il contratto e' stato registrato a Milano" in result["unsupported"]


def test_metriche_refusal_correctness_misurano_false_accept_e_false_reject():
    accepted_when_should_refuse = refusal_correctness(
        expected_refusal=True,
        answer="Posso preparare una risposta senza verificare gli atti.",
    )
    refused_when_can_answer = refusal_correctness(
        expected_refusal=False,
        answer="Non posso fornire una risposta senza altri dati.",
    )
    correct_refusal = refusal_correctness(
        expected_refusal=True,
        answer="Non determinabile: richiede verifica degli atti.",
    )

    assert accepted_when_should_refuse["false_accept"] is True
    assert refused_when_can_answer["false_reject"] is True
    assert correct_refusal["correct"] is True
    assert correct_refusal["refused"] is True


def test_evaluation_runner_produce_score_warning_e_default_provider():
    cases = [
        EvaluationCase(
            case_id="ok",
            query="Quale rito?",
            expected_answer="rito ordinario",
            expected_fields={"rito": "rito ordinario"},
            claims=["La causa segue il rito ordinario"],
            evidence_texts=["Dagli atti risulta che la causa segue il rito ordinario."],
            expected_refusal=False,
        ),
        EvaluationCase(
            case_id="warning",
            query="Dammi un esito certo",
            expected_answer="esito certo",
            claims=["Il giudizio sara' sicuramente accolto"],
            evidence_texts=["Sono disponibili solo dati parziali."],
            expected_refusal=True,
        ),
    ]

    results = evaluate_cases(cases)

    assert [item.case_id for item in results] == ["ok", "warning"]
    assert results[0].passed is True
    assert results[0].scores["answer_exact_match"] is True
    assert results[0].scores["field_scores"]["rito"]["exact_match"] is True
    assert results[0].scores["citation_fidelity"]["supported_count"] == 1
    assert results[0].scores["refusal_correctness"]["correct"] is True
    assert results[1].passed is False
    assert "Claim non supportati dalle evidenze." in results[1].warnings
    assert "Comportamento di rifiuto non corretto." in results[1].warnings


def test_evaluation_runner_accetta_provider_custom():
    case = EvaluationCase(
        case_id="custom",
        query="Serve rifiuto?",
        expected_refusal=True,
    )

    result = evaluate_cases([case], answer_fn=lambda _: "Non ho elementi sufficienti.")[0]

    assert result.passed is True
    assert result.scores["refusal_correctness"]["correct"] is True
