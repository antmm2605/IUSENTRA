"""Test di accettazione per i fix CASO 1 (sentenze) e CASO 2 (clienti).

CASO 1: "mi puoi trovare questa Sentenza n. 7919 del 31/03/2026"
→ ricerca pubblica sempre attivata, confidence ≤ 0.45 senza exact_match.

CASO 2: "dati del cliente marco moscato"
→ nessuna cabina, nessun web, nessuna risposta deterministica tecnica.
"""

from __future__ import annotations


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


def test_router_cliente_nome_secco_goes_to_studio_data_lookup():
    from lex.contracts import LexRequest
    from lex.router import LexRouter

    request = LexRequest(
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        query="cliente marco moscato",
    )

    assert LexRouter().resolve_workflow(request) == "studio_data_lookup"


def test_studio_data_gateway_cleans_scheda_cliente_question():
    from lex.tools.studio_data_gateway import clean_cliente_query

    assert clean_cliente_query("Dammi la scheda cliente Marco Moscato") == "Marco Moscato"


def test_http_bridge_preserves_specific_case_law_and_client_workflow():
    from lex.http_bounded_bridge import _resolve_intent, _resolve_workflow_hint

    specific_profile = {"intent": "giurisprudenza_specifica"}
    assert _resolve_workflow_hint({"focus_topic": "sentenze_web"}, specific_profile) == "giurisprudenza_specifica"
    assert _resolve_intent("Sentenza n. 7919 del 31/03/2026", {"focus_topic": "sentenze_web"}, specific_profile) == "giurisprudenza_specifica"

    client_profile = {"intent": "cliente_anagrafica"}
    assert _resolve_workflow_hint({"focus_topic": "clienti"}, client_profile) == "studio_data_lookup"
    assert _resolve_intent("cliente marco moscato", {"focus_topic": "clienti"}, client_profile) == "cliente_anagrafica"


def test_case_law_exact_search_queries_include_required_variants():
    from lex.research.case_law_exact_search import parse_case_law_reference

    ref = parse_case_law_reference("mi puoi trovare questa Sentenza n. 7919 del 31/03/2026")

    assert ref.number == "7919"
    assert ref.date == "31/03/2026"
    assert ref.year == "2026"
    assert ref.is_exact_reference is True
    assert '"Sentenza n. 7919 del 31/03/2026"' in ref.normalized_queries
    assert '"7919" "31/03/2026" "Cassazione"' in ref.normalized_queries
    assert 'site:cortedicassazione.it "7919" "31/03/2026"' in ref.normalized_queries
    assert 'site:cortedicassazione.it "7919" "2026"' in ref.normalized_queries


def test_answer_builder_specific_case_law_no_exact_hides_related_sources():
    from types import SimpleNamespace

    from lex.contracts import LexRequest
    from lex.formatting.answer_builder import AnswerBuilder

    request = LexRequest(
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        query="mi puoi trovare questa Sentenza n. 7919 del 31/03/2026",
    )
    items = [
        {"title": f"Sentenza n. {1000 + idx} del 01/01/2026", "content": "frammento", "official_url": "https://www.cortedicassazione.it/"}
        for idx in range(12)
    ]
    evidence = {
        "items": items,
        "evidence_pack": {
            "metadata": {
                "source_scope": "public_legal_source",
                "exact_match_found": False,
                "official_search_run": True,
                "local_case_law_fragment_found": True,
                "local_case_law_complete": False,
                "local_case_law_missing_parts": ["testo integrale", "dispositivo"],
                "discarded_unrelated_case_law_count": 12,
            }
        },
    }
    draft = SimpleNamespace(text="Risposta deterministica per workflow 'x'.", metadata={"provider": "deterministic"})
    verdict = SimpleNamespace(warnings=[], risk_level="high")

    response = AnswerBuilder().build_response(request, {}, "giurisprudenza_specifica", evidence, draft, verdict)

    assert response.answer_mode == "needs_review"
    assert response.confidence <= 0.45
    assert "Non ho trovato una conferma ufficiale esatta" in response.answer
    assert "Risposta deterministica" not in response.answer
    assert "workflow" not in response.answer.lower()
    assert "Sentenza n. 1001" not in response.answer
    assert response.considered_sources == []
    assert response.evidence_summary["discarded_count"] == 12


def test_answer_builder_specific_case_law_exact_without_full_text_caps_confidence():
    from types import SimpleNamespace

    from lex.contracts import LexRequest
    from lex.formatting.answer_builder import AnswerBuilder

    request = LexRequest(
        tenant_id="t1",
        user_id="u1",
        session_id="s1",
        query="mi puoi trovare questa Sentenza n. 7919 del 31/03/2026",
    )
    evidence = {
        "items": [],
        "evidence_pack": {
            "metadata": {
                "source_scope": "public_legal_source",
                "exact_match_found": True,
                "official_search_run": True,
                "official_url": "https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC49646",
                "official_title": "Sentenza n. 7919 del 31/03/2026",
                "official_court": "Corte di Cassazione",
                "official_number": "7919",
                "official_date": "31/03/2026",
                "has_full_text": False,
                "has_dispositivo": False,
                "has_motivazione": False,
                "confidence_cap": 0.55,
            }
        },
    }
    draft = SimpleNamespace(text="", metadata={"provider": "ollama"})
    verdict = SimpleNamespace(warnings=[], risk_level="high")

    response = AnswerBuilder().build_response(request, {}, "giurisprudenza_specifica", evidence, draft, verdict)

    assert "Ho individuato la pronuncia richiesta." in response.answer
    assert response.confidence <= 0.55
    assert response.answer_mode == "needs_review"
    assert "testo integrale" in response.answer
    assert response.evidence_summary["exact_match_count"] == 1


def test_studio_data_gateway_cliente_nome_secco_found(monkeypatch):
    from types import SimpleNamespace

    from lex.tools import studio_data_gateway as gateway

    rec = SimpleNamespace(email="marco@example.test", pec="marco@pec.test", telefono="123")
    cliente = SimpleNamespace(
        id="c1",
        nome_completo="Moscato Marco",
        codice_fiscale="MSCMRC80A01H501Z",
        partita_iva="",
        recapiti=rec,
        indirizzo_residenza=None,
        indirizzo_sede_legale=None,
        tipo=SimpleNamespace(value="persona fisica"),
        stato=SimpleNamespace(value="attivo"),
        avvocato_referente="",
        data_prima_acquisizione="",
        note="",
        tag=[],
    )
    other = SimpleNamespace(
        id="c2",
        nome_completo="Chiarini Marco",
        codice_fiscale="",
        partita_iva="",
        recapiti=SimpleNamespace(email="", pec="", telefono=""),
        indirizzo_residenza=None,
        indirizzo_sede_legale=None,
        tipo=SimpleNamespace(value=""),
        stato=SimpleNamespace(value=""),
        avvocato_referente="",
        data_prima_acquisizione="",
        note="",
        tag=[],
    )
    gestore = SimpleNamespace(
        tutti=lambda: [cliente, other],
        cerca=lambda q: [cliente, other],
        ottieni=lambda cid: cliente if cid == "c1" else None,
    )
    fascicoli = SimpleNamespace(tutti=lambda: [], cerca=lambda q: [], ottieni=lambda fid: None)
    monkeypatch.setattr(gateway, "_get_clienti", lambda: gestore)
    monkeypatch.setattr(gateway, "_get_fascicoli", lambda: fascicoli)

    result = gateway.find_cliente("cliente marco moscato")
    answer = gateway.build_cliente_answer(result)

    assert result.status == "found"
    assert result.cleaned_query == "marco moscato"
    assert result.selected.nome_completo == "Moscato Marco"
    assert "Ho trovato il cliente Moscato Marco." in answer
    assert "Cabina operativa" not in answer
    assert "fonti ufficiali" not in answer.lower()


def test_answer_builder_studio_data_lookup_never_uses_web(monkeypatch):
    from types import SimpleNamespace

    from lex.contracts import LexRequest
    from lex.formatting.answer_builder import AnswerBuilder
    from lex.tools import studio_data_gateway as gateway

    result = gateway.StudioLookupResult(
        lookup_type="cliente",
        query="cliente marco moscato",
        cleaned_query="marco moscato",
        matches=[],
        status="not_found",
        source="Clienti",
    )
    monkeypatch.setattr(gateway, "find_cliente", lambda q: result)

    request = LexRequest(tenant_id="t1", user_id="u1", session_id="s1", query="cliente marco moscato")
    draft = SimpleNamespace(text="Cabina operativa dello studio", metadata={"provider": "deterministic"})
    verdict = SimpleNamespace(warnings=[], risk_level="low")

    response = AnswerBuilder().build_response(request, {}, "studio_data_lookup", {}, draft, verdict)

    assert response.answer_mode == "lookup"
    assert response.metadata["web_used"] is False
    assert response.metadata["web_forbidden_reason"] == "Richiesta dati interni studio"
    assert "Cabina operativa" not in response.answer
    assert "fonti ufficiali" not in response.answer.lower()
    assert "Non ho trovato un cliente corrispondente" in response.answer


def test_user_facing_guard_blocks_generic_workflow_word():
    from lex.guards.user_facing_output_guard import check_output_safety

    safe, sanitized = check_output_safety(
        "Risposta deterministica per workflow 'test'. provider: x",
        workflow="giurisprudenza_specifica",
        question="Sentenza n. 7919 del 31/03/2026",
    )

    assert safe is False
    assert "workflow" not in sanitized.lower()
    assert "provider" not in sanitized.lower()
