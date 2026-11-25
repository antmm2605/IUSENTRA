from __future__ import annotations

import pytest

from lex.guards.exact_legal_reference_guard import (
    ExactLegalReferenceGuard,
    format_exact_reference_response,
)
from lex.research.case_law_reference_parser import ExactLegalReference


@pytest.fixture
def reference():
    return ExactLegalReference(
        kind="ordinanza",
        number="12345",
        date="",
        year="2024",
        court="Corte di Cassazione",
        section="lavoro",
        jurisdiction="civile",
        is_exact_reference=True,
        raw_query="Cassazione, ordinanza 12345/2024",
    )


@pytest.fixture
def official():
    return {
        "id": "indice",
        "title": "Ordinanza n. 12345/2024",
        "url": "https://www.cortedicassazione.it/indice/12345",
    }


def test_una_fonte_correlata_non_dimostra_il_testo_integrale(reference, official):
    verdict = ExactLegalReferenceGuard().check(
        reference=reference,
        evidence_items=[
            official,
            {
                "id": "commento",
                "title": "Ordinanza n. 12345/2024",
                "url": "https://example.test/commento",
                "excerpt": "Il dispositivo, secondo il commentatore.",
            },
        ],
    )

    assert verdict.exact_match_found
    assert not verdict.full_text_available
    assert verdict.confidence_cap == 0.55
    assert verdict.verdict.risk_level == "medium"
    assert verdict.primary_source["source_id"] == "indice"
    assert "testo integrale / dispositivo non disponibile" in format_exact_reference_response(verdict)


def test_il_testo_ufficiale_prevale_sulla_scheda_di_indice(reference, official):
    integrale = {
        **official,
        "id": "provvedimento",
        "url": "https://www.cortedicassazione.it/decisioni/12345",
        "text": "Motivi della decisione. P.Q.M. La Corte rinvia.",
    }
    verdict = ExactLegalReferenceGuard().check(
        reference=reference, evidence_items=[official, integrale]
    )

    assert verdict.full_text_available
    assert verdict.confidence_cap == 0.85
    assert verdict.verdict.risk_level == "low"
    assert verdict.primary_source["source_id"] == "provvedimento"
    assert verdict.missing_evidence == []
    assert integrale["url"] in format_exact_reference_response(verdict)


def test_anno_diverso_non_conferma_la_pronuncia(reference, official):
    risultati = [
        {**official, "title": f"Ordinanza n. 12345/{anno}"}
        for anno in ("2023", "2022", "2021")
    ]
    verdict = ExactLegalReferenceGuard().check(reference=reference, evidence_items=risultati)

    assert not verdict.exact_match_found
    assert verdict.primary_source is None
    assert verdict.confidence_cap == 0.45
    assert len(verdict.related_sources) == 2
    risposta = format_exact_reference_response(verdict)
    assert "Non ho trovato una conferma ufficiale esatta" in risposta
    assert "12345/2023" in risposta
    assert "12345/2021" not in risposta
