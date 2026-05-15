"""Dry-run dogfood scenarios for the Legal Source Engine."""

from __future__ import annotations

from .answer_policy import AnswerPolicy
from .citations import deduplicate_citations
from .models import DogfoodResult, DogfoodScenario, LegalAnswerDraft, LegalCitation, RetrievedLegalPassage


def _fixture_citation(
    *,
    source_id: str,
    source_name: str,
    source_category: str,
    document_type: str,
    title: str,
    date: str = "2026-01-01",
    version_date: str = "2026-01-01",
    url: str = "fixture://legal-source",
    authority: str = "",
    number: str = "FIX-1",
) -> LegalCitation:
    return LegalCitation(
        source_id=source_id,
        source_name=source_name,
        source_category=source_category,
        jurisdiction="IT" if source_category != "eu_law" else "EU",
        document_type=document_type,
        authority=authority or source_name,
        title=title,
        number=number,
        date=date,
        version_date=version_date,
        url=url,
        retrieved_at="2026-05-15T00:00:00+02:00",
    )


def example_dogfood_scenarios() -> list[DogfoodScenario]:
    normative_passage = RetrievedLegalPassage(
        text="Fixture normativa non reale: il testo dimostrativo richiede una citazione completa.",
        citation=_fixture_citation(
            source_id="normattiva",
            source_name="Normattiva",
            source_category="primary_legislation",
            document_type="legge",
            title="Atto dimostrativo non reale",
            url="fixture://normattiva/atto-demo",
        ),
        score=0.82,
        retrieval_method="fixture",
        source_priority=100,
    )
    no_version_passage = RetrievedLegalPassage(
        text="Fixture normativa non reale senza data di versione.",
        citation=_fixture_citation(
            source_id="normattiva",
            source_name="Normattiva",
            source_category="primary_legislation",
            document_type="legge",
            title="Atto dimostrativo senza versione",
            version_date="",
            url="fixture://normattiva/no-version",
        ),
        score=0.7,
        retrieval_method="fixture",
        source_priority=100,
    )
    practice_passage = RetrievedLegalPassage(
        text="Fixture prassi non reale: il documento va distinto dalla normativa primaria.",
        citation=_fixture_citation(
            source_id="agenzia_entrate",
            source_name="Agenzia delle Entrate",
            source_category="tax_practice",
            document_type="interpello",
            title="Risposta dimostrativa non reale",
            url="fixture://agenzia-entrate/interpello-demo",
        ),
        score=0.74,
        retrieval_method="fixture",
        source_priority=74,
    )
    return [
        DogfoodScenario(
            scenario_id="fixture_normativa_citata",
            question="Spiega il contenuto della fonte dimostrativa citata.",
            expected_source_types=["primary_legislation"],
            required_citation_fields=["source_id", "source_name", "document_type", "title", "date", "url"],
            fixture_passages=[normative_passage],
            should_answer=True,
        ),
        DogfoodScenario(
            scenario_id="nessun_passaggio",
            question="Posso avere una risposta giuridica senza fonti?",
            expected_source_types=["primary_legislation"],
            fixture_passages=[],
            should_answer=False,
            expected_refusal_reason="missing_retrieved_passages",
        ),
        DogfoodScenario(
            scenario_id="vigente_senza_versione",
            question="Qual e' il diritto vigente sulla fonte dimostrativa?",
            expected_source_types=["primary_legislation"],
            fixture_passages=[no_version_passage],
            should_answer=False,
            expected_refusal_reason="version_date_required",
        ),
        DogfoodScenario(
            scenario_id="prassi_non_normativa",
            question="La risposta dimostrativa dell'autorita fiscale vale come legge?",
            expected_source_types=["tax_practice"],
            fixture_passages=[practice_passage],
            should_answer=True,
        ),
        DogfoodScenario(
            scenario_id="azione_legale_rifiutata",
            question="Invia una PEC sulla base della fonte dimostrativa.",
            expected_source_types=["primary_legislation"],
            fixture_passages=[normative_passage],
            should_answer=False,
            expected_refusal_reason="lawyer_review_required",
        ),
    ]


def run_dogfood_scenario(scenario: DogfoodScenario, *, answer_policy: AnswerPolicy | None = None) -> DogfoodResult:
    policy = answer_policy or AnswerPolicy()
    citations = deduplicate_citations(passage.citation for passage in scenario.fixture_passages)
    draft = LegalAnswerDraft(
        question=scenario.question,
        answer="Risposta dry-run fondata solo sui passaggi fixture recuperati.",
        passages=list(scenario.fixture_passages),
        citations=citations,
        confidence=0.75 if scenario.fixture_passages else 0.0,
    )
    policy_result = policy.validate(draft)
    policy_codes = [error.code for error in policy_result.errors]
    warning_codes = [warning.code for warning in policy_result.warnings]
    citations_valid = all(passage.has_valid_citation() for passage in scenario.fixture_passages)
    source_types_ok = all(
        passage.citation.source_category in scenario.expected_source_types
        for passage in scenario.fixture_passages
    ) if scenario.expected_source_types and scenario.fixture_passages else True
    required_fields_ok = _required_fields_present(scenario)
    expected_refusal_ok = (
        not scenario.expected_refusal_reason
        or scenario.expected_refusal_reason in policy_codes
        or scenario.expected_refusal_reason in warning_codes
    )
    answer_allowed = policy_result.allowed
    passed = (
        answer_allowed is scenario.should_answer
        and citations_valid
        and source_types_ok
        and required_fields_ok
        and expected_refusal_ok
    )
    notes = [warning.message for warning in policy_result.warnings]
    return DogfoodResult(
        scenario_id=scenario.scenario_id,
        passed=passed,
        answer_allowed=answer_allowed,
        citations_valid=citations_valid,
        policy_errors=policy_codes,
        notes=notes,
    )


def run_dogfood_scenarios(scenarios: list[DogfoodScenario] | None = None) -> list[DogfoodResult]:
    return [run_dogfood_scenario(scenario) for scenario in list(scenarios or example_dogfood_scenarios())]


def _required_fields_present(scenario: DogfoodScenario) -> bool:
    for passage in scenario.fixture_passages:
        citation = passage.citation
        for field_name in scenario.required_citation_fields:
            if not getattr(citation, field_name, ""):
                return False
    return True


__all__ = ["example_dogfood_scenarios", "run_dogfood_scenario", "run_dogfood_scenarios"]
