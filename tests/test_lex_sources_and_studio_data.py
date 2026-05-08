"""Test suite: Lex — fonti pubbliche e dati studio.

Verifica che:
1. Il parser estragga correttamente riferimenti esatti a sentenze
2. L'ExactLegalReferenceGuard classifichi correttamente le evidenze
3. Il source scope policy classifichi correttamente le query
4. Il router instradi `cliente_anagrafica` su `studio_data_lookup`
5. `_should_force_web_fallback` forzi web per sentenze esatte anche con contesto locale
6. `_extract_entity_hint_from_question` estragga CF/PIVA/email dalla domanda
7. Il debug payload includa i campi source_scope
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# TC-01: case_law_reference_parser — sentenza con numero e data
# ---------------------------------------------------------------------------

def test_parse_exact_sentenza_numero_data():
    from lex.research.case_law_reference_parser import parse_case_law_reference

    ref = parse_case_law_reference("mi puoi trovare la Sentenza n. 7919 del 31/03/2026")
    assert ref.is_exact_reference is True
    assert ref.number == "7919"
    assert ref.date == "31/03/2026"
    assert ref.year == "2026"
    assert ref.kind == "sentenza"


# ---------------------------------------------------------------------------
# TC-02: case_law_reference_parser — sentenza con solo anno
# ---------------------------------------------------------------------------

def test_parse_exact_sentenza_numero_anno():
    from lex.research.case_law_reference_parser import parse_case_law_reference

    ref = parse_case_law_reference("Sentenza Cassazione civile n. 12345/2025")
    assert ref.is_exact_reference is True
    assert ref.number == "12345"
    assert ref.year == "2025"


# ---------------------------------------------------------------------------
# TC-03: case_law_reference_parser — senza numero → not exact
# ---------------------------------------------------------------------------

def test_parse_no_number_returns_not_exact():
    from lex.research.case_law_reference_parser import parse_case_law_reference

    ref = parse_case_law_reference("dammi sentenze sulla prescrizione")
    assert ref.is_exact_reference is False


# ---------------------------------------------------------------------------
# TC-04: case_law_reference_parser — query variants generate sito cassazione
# ---------------------------------------------------------------------------

def test_cassazione_query_variants_generated():
    from lex.research.case_law_reference_parser import parse_case_law_reference

    ref = parse_case_law_reference("Sentenza n. 7919 del 31/03/2026")
    assert ref.cassazione_query_variants, "Deve generare almeno una query variant"
    assert any("cortedicassazione" in q.lower() for q in ref.cassazione_query_variants)


# ---------------------------------------------------------------------------
# TC-05: ExactLegalReferenceGuard — nessuna evidenza → not_found
# ---------------------------------------------------------------------------

def test_guard_no_evidence_not_found():
    from lex.research.case_law_reference_parser import parse_case_law_reference
    from lex.guards.exact_legal_reference_guard import ExactLegalReferenceGuard

    ref = parse_case_law_reference("Sentenza n. 7919 del 31/03/2026")
    guard = ExactLegalReferenceGuard()
    verdict = guard.check(reference=ref, evidence_items=[])
    assert verdict.exact_match_found is False
    assert verdict.confidence_cap <= 0.46


# ---------------------------------------------------------------------------
# TC-06: ExactLegalReferenceGuard — evidenza con numero ma senza testo → found_no_text
# ---------------------------------------------------------------------------

def test_guard_evidence_number_no_full_text():
    from lex.research.case_law_reference_parser import parse_case_law_reference
    from lex.guards.exact_legal_reference_guard import ExactLegalReferenceGuard

    ref = parse_case_law_reference("Sentenza n. 7919 del 31/03/2026")
    evidence = [
        {
            "text": "La sentenza n. 7919 del 31/03/2026 riguarda il contratto.",
            "url": "https://cortedicassazione.it/doc/7919",
            "title": "Cass. Sez. Civ. n. 7919/2026",
        }
    ]
    guard = ExactLegalReferenceGuard()
    verdict = guard.check(reference=ref, evidence_items=evidence)
    assert verdict.exact_match_found is True
    assert verdict.confidence_cap <= 0.86


# ---------------------------------------------------------------------------
# TC-07: source_scope_policy — query sentenza specifica → public_legal_source
# ---------------------------------------------------------------------------

def test_source_scope_exact_sentenza():
    from lex.research.source_scope_policy import classify_source_scope

    scope = classify_source_scope("trovami la Sentenza n. 7919 del 31/03/2026")
    assert scope.exact_legal_reference is True
    assert scope.requires_public_web is True
    assert scope.scope in ("public_legal_source", "mixed_private_public")


# ---------------------------------------------------------------------------
# TC-08: source_scope_policy — query cliente → studio_internal
# ---------------------------------------------------------------------------

def test_source_scope_cliente_anagrafica():
    from lex.research.source_scope_policy import classify_source_scope

    scope = classify_source_scope("dammi i dati del cliente Mario Rossi")
    assert scope.requires_studio_data is True
    assert scope.scope in ("studio_internal", "mixed_private_public")


# ---------------------------------------------------------------------------
# TC-09: LexRouter — cliente_anagrafica → studio_data_lookup
# ---------------------------------------------------------------------------

def test_router_cliente_anagrafica_workflow():
    from lex.router import LexRouter

    class FakeRequest:
        query = "dammi i dati del cliente Mario Rossi"
        intent = "cliente_anagrafica"
        workflow_hint = ""
        metadata = {}
        fascicolo_id = None

    router = LexRouter()
    workflow = router.resolve_workflow(FakeRequest())
    assert workflow == "studio_data_lookup"


# ---------------------------------------------------------------------------
# TC-10: LexRouter — routing testuale cliente dati
# ---------------------------------------------------------------------------

def test_router_textual_routing_cliente_dati():
    from lex.router import LexRouter

    class FakeRequest:
        query = "quali sono i recapiti del cliente Rossi"
        intent = ""
        workflow_hint = ""
        metadata = {}
        fascicolo_id = None

    router = LexRouter()
    workflow = router.resolve_workflow(FakeRequest())
    assert workflow == "studio_data_lookup"


# ---------------------------------------------------------------------------
# TC-11: extract_entity_hint — CF estratto
# ---------------------------------------------------------------------------

def test_extract_entity_hint_cf():
    from lex.research.query_helpers import extract_entity_hint

    result = extract_entity_hint("dati del cliente RSSMRA80A01H501Z")
    assert result["codice_fiscale"] == "RSSMRA80A01H501Z"


# ---------------------------------------------------------------------------
# TC-12: extract_entity_hint — email estratta
# ---------------------------------------------------------------------------

def test_extract_entity_hint_email():
    from lex.research.query_helpers import extract_entity_hint

    result = extract_entity_hint("contatti di mario.rossi@example.com")
    assert result["email"] == "mario.rossi@example.com"


# ---------------------------------------------------------------------------
# TC-13: is_exact_legal_reference_query — riconosce pattern correttamente
# ---------------------------------------------------------------------------

def test_is_exact_legal_reference_query_true():
    from lex.research.query_helpers import is_exact_legal_reference_query

    assert is_exact_legal_reference_query("sentenza n. 7919 del 31/03/2026") is True
    assert is_exact_legal_reference_query("n. 12345/2025 cassazione") is True
    assert is_exact_legal_reference_query("ordinanza n. 500 del 01/01/2024") is True


def test_is_exact_legal_reference_query_false():
    from lex.research.query_helpers import is_exact_legal_reference_query

    assert is_exact_legal_reference_query("dimmi delle sentenze sulla prescrizione") is False
    assert is_exact_legal_reference_query("giurisprudenza sul contratto") is False


# ---------------------------------------------------------------------------
# TC-14: debug payload — campi source_scope presenti
# ---------------------------------------------------------------------------

def test_debug_payload_source_scope_fields():
    from lex.formatting.debug_payload_builder import build_lex_debug_payload

    payload = build_lex_debug_payload(
        request=None,
        context=None,
        workflow="giurisprudenza_specifica",
        evidence={},
        draft=None,
        verdict=None,
        response=None,
        source_scope="public_legal_source",
        source_scope_confidence=0.9,
        exact_legal_reference=True,
        exact_reference_number="7919",
        exact_reference_date="31/03/2026",
        exact_reference_year="2026",
        exact_reference_court="Corte di Cassazione",
        exact_reference_kind="sentenza",
        exact_reference_verdict="not_found",
        web_forced_by_exact_ref=True,
        studio_data_lookup_used=False,
        studio_entity_hint="",
    )

    assert payload["source_scope"] == "public_legal_source"
    assert payload["exact_legal_reference"] is True
    assert payload["exact_reference_number"] == "7919"
    assert payload["web_forced_by_exact_ref"] is True
    assert "studio_data_lookup_used" in payload


# ---------------------------------------------------------------------------
# TC-15: studio_data_gateway — extract_entity_hint CF
# ---------------------------------------------------------------------------

def test_studio_gateway_entity_hint_cf():
    from lex.tools.studio_data_gateway import extract_entity_hint

    result = extract_entity_hint("dati di RSSMRA80A01H501Z")
    assert result["codice_fiscale"] == "RSSMRA80A01H501Z"


# ---------------------------------------------------------------------------
# TC-16: studio_data_gateway — extract_entity_hint email
# ---------------------------------------------------------------------------

def test_studio_gateway_entity_hint_email():
    from lex.tools.studio_data_gateway import extract_entity_hint

    result = extract_entity_hint("trova il cliente con email test@studio.it")
    assert result["email"] == "test@studio.it"
