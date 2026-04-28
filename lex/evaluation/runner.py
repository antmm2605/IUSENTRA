"""Runner minimale per quality gate Lex in CI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .metrics import citation_fidelity, exact_match, refusal_correctness, token_f1


@dataclass(slots=True)
class EvaluationCase:
    case_id: str
    query: str
    expected_answer: str = ""
    expected_fields: dict[str, str] = field(default_factory=dict)
    claims: list[str] = field(default_factory=list)
    evidence_texts: list[str] = field(default_factory=list)
    expected_refusal: bool = False


@dataclass(slots=True)
class EvaluationResult:
    case_id: str
    passed: bool
    scores: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


AnswerFn = Callable[[EvaluationCase], str]


def _default_answer(case: EvaluationCase) -> str:
    return case.expected_answer


def evaluate_cases(cases: list[EvaluationCase], answer_fn: AnswerFn | None = None) -> list[EvaluationResult]:
    """Valuta casi interni senza dipendere da benchmark remoti."""

    provider = answer_fn or _default_answer
    results: list[EvaluationResult] = []
    for case in cases:
        answer = provider(case)
        scores: dict[str, object] = {}
        warnings: list[str] = []

        if case.expected_answer:
            scores["answer_exact_match"] = exact_match(case.expected_answer, answer)
            scores["answer_token_f1"] = token_f1(case.expected_answer, answer)
        if case.expected_fields:
            field_scores = {
                field: {
                    "exact_match": exact_match(expected, answer),
                    "token_f1": token_f1(expected, answer),
                }
                for field, expected in case.expected_fields.items()
            }
            scores["field_scores"] = field_scores
        if case.claims or case.evidence_texts:
            citation = citation_fidelity(case.claims, case.evidence_texts)
            scores["citation_fidelity"] = citation
            if citation["unsupported"]:
                warnings.append("Claim non supportati dalle evidenze.")
        refusal = refusal_correctness(expected_refusal=case.expected_refusal, answer=answer)
        scores["refusal_correctness"] = refusal
        if not refusal["correct"]:
            warnings.append("Comportamento di rifiuto non corretto.")

        passed = not warnings
        results.append(EvaluationResult(case_id=case.case_id, passed=passed, scores=scores, warnings=warnings))
    return results
