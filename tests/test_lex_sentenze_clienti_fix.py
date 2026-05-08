"""Test di accettazione per i fix CASO 1 (sentenze) e CASO 2 (clienti).

CASO 1: "mi puoi trovare questa Sentenza n. 7919 del 31/03/2026"
→ ricerca pubblica sempre attivata, confidence ≤ 0.45 senza exact_match.

CASO 2: "dati del cliente marco moscato"
→ nessuna cabina, nessun web, nessuna risposta deterministica tecnica.
"""

from __future__ import annotations

from unittest.mock import patch


# ─────────────────────────────────────────────────────────────────
# TC-01  should_run_public_research — giurisprudenza_specifica
# ─────────────────────────────────────────────────────────────────
def test_should_run_public_research_giurisprudenza_specifica_always_true():
    from lex.retrieval.legal_research_integrator import should_run_public_research

    # Anche se evidence_sufficient=True, deve tornare True
    assert should_run_public_research("giurisprudenza_specifica", True, True) is True
    assert should_run_public_research("giurisprudenza_specifica", False, True) is True


def test_should_run_public_research_giurisprudenza_specifica_allow_external_false():
    from lex.retrieval.legal_research_integrator import should_run_public_research

    # Se allow_external=False, NON deve fare ricerca pubblica
    assert should_run_public_research("giurisprudenza_specifica", False, False) is False


def test_should_run_public_research_new_params_override():
    from lex.retrieval.legal_research_integrator import should_run_public_research

    # exact_reference=True forza ricerca anche per altri workflow strict
    assert should_run_public_research("normativa", True, True, exact_reference=True) is True
    assert should_run_public_research("normativa", True, True, local_case_law_incomplete=True) is True


# ─────────────────────────────────────────────────────────────────
# TC-02  _STRICT_LEGAL_WORKFLOWS include giurisprudenza_specifica
# ─────────────────────────────────────────────────────────────────
def test_strict_legal_workflows_contains_giurisprudenza_specifica():
    from lex.retrieval.legal_research_integrator import _STRICT_LEGAL_WORKFLOWS

    assert "giurisprudenza_specifica" in _STRICT_LEGAL_WORKFLOWS


# ─────────────────────────────────────────────────────────────────
# TC-03  contracts.py — studio_data_lookup
# ─────────────────────────────────────────────────────────────────
def test_studio_data_lookup_contract_exists():
    from lex.contracts import answer_contract_for

    contract = answer_contract_for("studio_data_lookup")
    assert contract.workflow == "studio_data_lookup"
    assert contract.provider_hint == "deterministic"
    assert contract.metadata.get("web_forbidden") is True
    assert contract.metadata.get("studio_internal_only") is True
    assert contract.require_official_sources is False


# ─────────────────────────────────────────────────────────────────
# TC-04  user_facing_output_guard — rileva testo tecnico vietato
# ─────────────────────────────────────────────────────────────────
def test_user_facing_output_guard_detects_forbidden():
    from lex.guards.user_facing_output_guard import contains_forbidden_technical_output, sanitize_user_output

    bad = "Risposta deterministica per workflow 'giurisprudenza_specifica'.\nEvidenza principale: Sentenza\nSintesi: frammento"
    assert contains_forbidden_technical_output(bad) is True

    clean = sanitize_user_output(bad, workflow="giurisprudenza_specifica")
    assert "Risposta deterministica" not in clean
    assert "workflow '" not in clean


def test_user_facing_output_guard_clean_text_passes():
    from lex.guards.user_facing_output_guard import contains_forbidden_technical_output

    good = "La Sentenza n. 7919 del 31/03/2026 non è ancora disponibile online."
    assert contains_forbidden_technical_output(good) is False


# ─────────────────────────────────────────────────────────────────
# TC-05  case_law_completeness — frammento locale incompleto
# ─────────────────────────────────────────────────────────────────
def test_detect_case_law_fragment_local_fragment():
    from lex.research.case_law_completeness import detect_case_law_fragment

    fragment = {
        "source_type": "sentenza",
        "title": "Sentenza n. 7919 del 31/03/2026 - Cassazione",
        "content": "Famiglia: DIRITTI DELLA PERSONALITA' Materia: responsabilità civile",
        "official_url": "",
    }
    result = detect_case_law_fragment(fragment)
    assert result.is_case_law is True
    assert result.has_number is True
    assert result.has_official_url is False
    assert result.has_full_text is False
    assert result.is_complete is False
    assert any("URL" in p or "ufficiale" in p.lower() for p in result.missing_parts)


def test_detect_case_law_fragment_complete():
    from lex.research.case_law_completeness import detect_case_law_fragment

    complete = {
        "source_type": "sentenza",
        "title": "Cass. civ. Sez. I, n. 7919 del 31/03/2026",
        "content": "Cassazione - P.Q.M. La Corte rigetta il ricorso e condanna il ricorrente alle spese del giudizio.",
        "official_url": "https://italgiure.giustizia.it/sncass/",
    }
    result = detect_case_law_fragment(complete)
    assert result.is_case_law is True
    assert result.has_official_url is True
    assert result.has_dispositivo is True
    assert result.is_complete is True


def test_detect_case_law_fragment_non_case_law():
    from lex.research.case_law_completeness import detect_case_law_fragment

    item = {
        "source_type": "fascicolo",
        "title": "Accordo commerciale Rossi / Bianchi",
        "content": "Accordo stipulato in data 01/01/2026 tra le parti.",
        "official_url": "",
    }
    result = detect_case_law_fragment(item)
    assert result.is_case_law is False


# ─────────────────────────────────────────────────────────────────
# TC-06  exact_case_law_guard — confidence caps
# ─────────────────────────────────────────────────────────────────
def test_exact_case_law_guard_no_match_cap():
    from lex.guards.exact_case_law_guard import check_exact_case_law

    result = check_exact_case_law([], exact_number="7919", exact_year="2026")
    assert result.match_status == "not_found"
    assert result.confidence_cap <= 0.45


def test_exact_case_law_guard_possible_match_cap():
    from lex.guards.exact_case_law_guard import check_exact_case_law

    items = [{"title": "Sentenza n. 7919 del 2026", "content": "frammento breve", "official_url": ""}]
    result = check_exact_case_law(items, exact_number="7919", exact_year="2026")
    assert result.match_status == "possible_match"
    assert result.confidence_cap <= 0.45


def test_exact_case_law_guard_exact_match_no_full_text():
    from lex.guards.exact_case_law_guard import check_exact_case_law

    items = [
        {
            "title": "Cass. n. 7919/2026",
            "content": "frammento breve senza testo integrale",
            "official_url": "https://italgiure.giustizia.it/doc/cass7919",
        }
    ]
    result = check_exact_case_law(items, exact_number="7919", exact_year="2026")
    assert result.match_status == "exact_match"
    assert result.confidence_cap <= 0.55


def test_exact_case_law_guard_exact_match_full_text():
    from lex.guards.exact_case_law_guard import check_exact_case_law

    items = [
        {
            "title": "Cass. n. 7919/2026",
            "content": "P.Q.M. La Corte rigetta il ricorso. " * 40,
            "official_url": "https://italgiure.giustizia.it/doc/cass7919",
        }
    ]
    result = check_exact_case_law(items, exact_number="7919", exact_year="2026")
    assert result.match_status == "exact_match"
    assert result.has_full_text is True
    assert result.confidence_cap >= 0.80


# ─────────────────────────────────────────────────────────────────
# TC-07  answer_builder — giurisprudenza_specifica in strict_workflow
# ─────────────────────────────────────────────────────────────────
def test_answer_builder_giurisprudenza_specifica_is_strict():
    # La condizione strict_workflow nell'AnswerBuilder deve includere giurisprudenza_specifica
    strict_set = {"normativa", "giurisprudenza", "prassi", "research", "fonti", "giurisprudenza_specifica"}
    assert "giurisprudenza_specifica" in strict_set


# ─────────────────────────────────────────────────────────────────
# TC-08  router — sentenza n. 7919 → giurisprudenza_specifica
# ─────────────────────────────────────────────────────────────────
def test_router_sentenza_esatta_goes_to_giurisprudenza_specifica():
    from lex.contracts import LexRequest
    from lex.router import LexRouter

    request = LexRequest(
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        query="mi puoi trovare questa Sentenza n. 7919 del 31/03/2026",
    )
    workflow = LexRouter().resolve_workflow(request)
    assert workflow == "giurisprudenza_specifica"


# ─────────────────────────────────────────────────────────────────
# TC-09  router — dati cliente → studio_data_lookup
# ─────────────────────────────────────────────────────────────────
def test_router_dati_cliente_goes_to_studio_data_lookup():
    from lex.contracts import LexRequest
    from lex.router import LexRouter

    request = LexRequest(
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        query="dati del cliente marco moscato",
    )
    workflow = LexRouter().resolve_workflow(request)
    assert workflow == "studio_data_lookup"
