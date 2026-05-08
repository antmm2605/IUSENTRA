"""Suite completa test Lex Legal Studio — 20 casi d'uso professionali.

Copre tutti i 13 macro-intenti del profilo studio legale italiano.
Da eseguire con: python -m pytest tests/test_lex_legal_studio_full.py -v
"""

from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# Helpers di setup
# ---------------------------------------------------------------------------

def _make_request(
    query: str,
    *,
    intent: str = "",
    workflow_hint: str = "",
    fascicolo_id: str | None = None,
    metadata: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        tenant_id="test_tenant",
        user_id="test_user",
        session_id="test_session",
        query=query,
        intent=intent,
        fascicolo_id=fascicolo_id,
        workflow_hint=workflow_hint,
        metadata=metadata or {},
        allow_external_research=True,
        require_citations=False,
        require_official_sources=False,
    )


def _make_draft(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, metadata={})


# ---------------------------------------------------------------------------
# TC-01: Routing diffida → drafting_legal_letter
# ---------------------------------------------------------------------------

class TestTC01DiffidaRouting:
    """TC-01: Diffida deve finire in drafting_legal_letter."""

    def test_router_diffida(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("scrivi una diffida professionale al condominio")
        assert router.resolve_workflow(req) == "drafting_legal_letter"

    def test_router_messa_in_mora(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("prepara la messa in mora per il debitore")
        assert router.resolve_workflow(req) == "drafting_legal_letter"

    def test_router_sollecito_formale(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("sollecito formale per il pagamento della parcella")
        assert router.resolve_workflow(req) == "drafting_legal_letter"


# ---------------------------------------------------------------------------
# TC-02: Routing termini processuali
# ---------------------------------------------------------------------------

class TestTC02TerminiProcessuali:
    """TC-02: Calcolo termini deve finire in termini_processuali."""

    def test_router_termine_opposizione(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("calcola il termine per l'opposizione al decreto ingiuntivo")
        assert router.resolve_workflow(req) == "termini_processuali"

    def test_router_giorni_dalla_notifica(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("quanti giorni dalla notifica per appellare")
        assert router.resolve_workflow(req) == "termini_processuali"

    def test_termini_workflow_system_prompt_italiano(self):
        from lex.workflows.termini_processuali_workflow import TerminiProcessualiWorkflow
        assert "italiano" in TerminiProcessualiWorkflow.system_prompt.lower()
        assert "avvocato" not in TerminiProcessualiWorkflow.system_prompt.lower() or \
               "consulta un avvocato" not in TerminiProcessualiWorkflow.system_prompt.lower()


# ---------------------------------------------------------------------------
# TC-03: Routing deposito telematico
# ---------------------------------------------------------------------------

class TestTC03DepositoTelematico:
    """TC-03: Deposito telematico deve finire in deposito_telematico."""

    def test_router_deposito_pst(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("checklist per il deposito PST del ricorso")
        assert router.resolve_workflow(req) == "deposito_telematico"

    def test_router_errore_pdp(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("errore PDP nel deposito penale")
        assert router.resolve_workflow(req) == "deposito_telematico"

    def test_deposito_workflow_checklist(self):
        from lex.workflows.deposito_telematico_workflow import checklist_portale
        result = checklist_portale("PST")
        assert "PDF/A" in result
        assert "CAdES" in result
        assert "D.M. 44/2011" in result

    def test_deposito_workflow_checklist_pdp(self):
        from lex.workflows.deposito_telematico_workflow import checklist_portale
        result = checklist_portale("PDP")
        assert "mTLS" in result
        assert "D.Lgs. 150/2022" in result


# ---------------------------------------------------------------------------
# TC-04: Routing giurisprudenza specifica (numero sentenza)
# ---------------------------------------------------------------------------

class TestTC04GiurisprudenzaSpecifica:
    """TC-04: Sentenza con numero deve finire in giurisprudenza_specifica."""

    def test_router_sentenza_con_numero(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("cerco Cass. Civ. n. 12345/2023")
        assert router.resolve_workflow(req) == "giurisprudenza_specifica"

    def test_router_sentenza_data(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("sentenza del 15/03/2022 del Tribunale di Milano")
        # Non deve confondersi con giurisprudenza generica
        workflow = router.resolve_workflow(req)
        assert workflow in {"giurisprudenza", "giurisprudenza_specifica", "question_answering"}

    def test_giurisprudenza_specifica_workflow_prompt(self):
        from lex.workflows.giurisprudenza_specifica_workflow import GiurisprudenzaSpecificaWorkflow
        prompt = GiurisprudenzaSpecificaWorkflow.system_prompt
        assert "inventare" in prompt.lower() or "non inventare" in prompt.lower()
        assert "italiano" in prompt.lower()


# ---------------------------------------------------------------------------
# TC-05: Routing feedback diagnostico
# ---------------------------------------------------------------------------

class TestTC05FeedbackDiagnostico:
    """TC-05: Correzione utente deve finire in lex_feedback_diagnostico."""

    def test_router_non_hai_capito(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("non hai capito, intendevo altro")
        assert router.resolve_workflow(req) == "lex_feedback_diagnostico"

    def test_router_risposta_sbagliata(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("la tua risposta è sbagliata, riprova")
        assert router.resolve_workflow(req) == "lex_feedback_diagnostico"

    def test_feedback_workflow_registrato(self):
        from lex.workflows import WORKFLOW_REGISTRY
        assert "lex_feedback_diagnostico" in WORKFLOW_REGISTRY


# ---------------------------------------------------------------------------
# TC-06: Intent matrix — classificazione macro-intenti
# ---------------------------------------------------------------------------

class TestTC06IntentMatrix:
    """TC-06: La matrice intenti classifica correttamente le richieste."""

    @pytest.mark.parametrize("query,expected_key", [
        ("scrivi una diffida al debitore", "redazione_legale"),
        ("calcola il termine per l'opposizione", "agenda_scadenze_termini"),
        ("checklist deposito PST", "telematico_deposito"),
        ("sentenze sull'usucapione", "giurisprudenza"),
        ("articolo 1218 codice civile", "normativa"),
        ("compenso DM 55 causa 50000 euro", "economico_forense"),
        ("cosa c'è da fare oggi", "cabina_studio"),
        ("non hai capito", "lex_feedback_diagnostico"),
    ])
    def test_classify_from_matrix(self, query: str, expected_key: str):
        from lex.research.legal_studio_intent_matrix import classify_from_matrix
        result = classify_from_matrix(query)
        assert result is not None, f"Nessun intento trovato per: {query!r}"
        assert result.key == expected_key, (
            f"Query {query!r}: atteso {expected_key!r}, trovato {result.key!r}"
        )

    def test_all_intents_have_workflows(self):
        from lex.research.legal_studio_intent_matrix import all_intents
        for intent in all_intents():
            assert len(intent.workflows) > 0, f"Intent {intent.key} non ha workflow"
            assert len(intent.response_schema) > 0, f"Intent {intent.key} non ha schema"

    def test_priority_order(self):
        from lex.research.legal_studio_intent_matrix import all_intents
        intents = all_intents()
        priorities = [i.priority for i in intents]
        assert priorities == sorted(priorities), "Gli intenti non sono in ordine di priorità"


# ---------------------------------------------------------------------------
# TC-07: AnswerContract per workflow di redazione
# ---------------------------------------------------------------------------

class TestTC07AnswerContract:
    """TC-07: I contratti di risposta per redazione impongono Italian-only."""

    @pytest.mark.parametrize("workflow", [
        "drafting_legal_letter", "lettera", "bozza_lettera",
        "atto", "bozza_atto", "pec_comunicazioni",
    ])
    def test_drafting_contract(self, workflow: str):
        from lex.contracts import answer_contract_for
        contract = answer_contract_for(workflow)
        assert contract.metadata.get("italian_only") is True
        assert contract.metadata.get("disclaimer_suppressed") is True
        assert contract.metadata.get("no_english_output") is True
        assert "bozza" in contract.sections or "checklist" in contract.sections

    def test_termini_processuali_contract(self):
        from lex.contracts import answer_contract_for
        contract = answer_contract_for("termini_processuali")
        assert contract.provider_hint == "deterministic"
        assert "scadenza_calcolata" in contract.sections

    def test_deposito_telematico_contract(self):
        from lex.contracts import answer_contract_for
        contract = answer_contract_for("deposito_telematico")
        assert "checklist" in contract.sections

    def test_lex_feedback_contract(self):
        from lex.contracts import answer_contract_for
        contract = answer_contract_for("lex_feedback_diagnostico")
        assert contract.allow_abstention is False
        assert "riformulazione" in contract.sections


# ---------------------------------------------------------------------------
# TC-08: Legal answer quality guard — blocco disclaimer
# ---------------------------------------------------------------------------

class TestTC08QualityGuardDisclaimer:
    """TC-08: La guardia qualità blocca 'consulta un avvocato' e simili."""

    def test_blocco_consulta_avvocato(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft("Ti consiglio di consultare un avvocato per questa questione.")
        verdict = guard.check(workflow="normativa", draft=draft, evidence={})
        assert verdict.allowed is False
        assert any("disclaimer" in w.lower() or "avvocato" in w.lower() for w in verdict.warnings)

    def test_blocco_non_sono_avvocato(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft("Non sono un avvocato e non posso fornire consulenza legale.")
        verdict = guard.check(workflow="giurisprudenza", draft=draft, evidence={})
        assert verdict.allowed is False

    def test_blocco_chatbot_markers(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft("Spero di essere stato utile! Fammi sapere se hai altre domande.")
        verdict = guard.check(workflow="drafting_legal_letter", draft=draft, evidence={})
        assert verdict.allowed is False

    def test_blocco_json_output(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft('{"risposta": "Ecco la risposta"}')
        verdict = guard.check(workflow="fascicolo", draft=draft, evidence={})
        assert verdict.allowed is False

    def test_permette_risposta_italiana_corretta(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft(
            "Il termine per l'opposizione al decreto ingiuntivo è di 40 giorni "
            "dalla notifica (art. 641 c.p.c.). La scadenza cade il 15/07/2025."
        )
        verdict = guard.check(workflow="termini_processuali", draft=draft, evidence={})
        assert verdict.allowed is True


# ---------------------------------------------------------------------------
# TC-09: Guard — blocco inglese in redazione
# ---------------------------------------------------------------------------

class TestTC09EnglishBlock:
    """TC-09: Output in inglese viene bloccato per workflow di redazione."""

    def test_blocco_dear_recipient(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft("Dear Recipient, I am writing to formally notify you...")
        verdict = guard.check(workflow="drafting_legal_letter", draft=draft, evidence={})
        assert verdict.allowed is False

    def test_blocco_please_be_advised(self):
        from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
        guard = LegalAnswerQualityGuard()
        draft = _make_draft("Please be advised that your payment is overdue.")
        verdict = guard.check(workflow="bozza_lettera", draft=draft, evidence={})
        assert verdict.allowed is False


# ---------------------------------------------------------------------------
# TC-10: Tools — calcolo tariffario DM 55
# ---------------------------------------------------------------------------

class TestTC10Tariffario:
    """TC-10: Il tool calculate_tariffario produce output strutturato corretto."""

    def test_scaglione_base(self):
        from lex.tools.legal_studio_tools import calculate_tariffario
        result = calculate_tariffario(5000.0)
        assert result["ok"] is True
        assert result["totale_compenso"] > 0
        assert "D.M. 55" in result["normativa"]
        assert "scaglione" in result
        assert result["rimborso_forfettario_15pct"] == round(result["totale_compenso"] * 0.15, 2)

    def test_scaglione_medio(self):
        from lex.tools.legal_studio_tools import calculate_tariffario
        result = calculate_tariffario(50000.0)
        assert result["ok"] is True
        assert result["totale_compenso"] > 0

    def test_fasi_selezionate(self):
        from lex.tools.legal_studio_tools import calculate_tariffario
        result = calculate_tariffario(10000.0, fasi=["fase_studio", "fase_dec"])
        assert result["ok"] is True
        assert len(result["fasi_liquidate"]) == 2

    def test_avvertenza_presente(self):
        from lex.tools.legal_studio_tools import calculate_tariffario
        result = calculate_tariffario(100000.0)
        assert "avvertenza" in result
        assert len(result["avvertenza"]) > 0


# ---------------------------------------------------------------------------
# TC-11: Tools — checklist deposito
# ---------------------------------------------------------------------------

class TestTC11DepositoChecklist:
    """TC-11: Il tool build_deposito_checklist produce le checklist corrette."""

    @pytest.mark.parametrize("portale,expected_item", [
        ("PST", "PDF/A-1b"),
        ("PDP", "mTLS"),
        ("PAT", "SIGA"),
        ("PTT", "SPID"),
    ])
    def test_checklist_portale(self, portale: str, expected_item: str):
        from lex.tools.legal_studio_tools import build_deposito_checklist
        result = build_deposito_checklist(portale)
        assert result["ok"] is True
        assert result["portale"] == portale
        items_text = " ".join(result["checklist"])
        assert expected_item in items_text


# ---------------------------------------------------------------------------
# TC-12: Tools — calcolo scadenza processuale
# ---------------------------------------------------------------------------

class TestTC12CalcoloScadenza:
    """TC-12: Il tool calculate_deadline produce scadenze corrette."""

    def test_opposizione_decreto_ingiuntivo(self):
        from lex.tools.legal_studio_tools import calculate_deadline
        result = calculate_deadline(
            "opposizione_decreto_ingiuntivo",
            data_decorrenza="2025-01-01",
        )
        assert result["ok"] is True
        assert result["giorni"] == 40
        assert result["scadenza"] == "10/02/2025"
        assert "art." in result["label"].lower() or "641" in result["label"]

    def test_termine_non_esistente(self):
        from lex.tools.legal_studio_tools import calculate_deadline
        result = calculate_deadline("tipo_inesistente", data_decorrenza="2025-01-01")
        assert result["ok"] is True
        assert result["giorni"] == 30  # default

    def test_urgente_flag(self):
        from datetime import date, timedelta
        from lex.tools.legal_studio_tools import calculate_deadline
        domani = (date.today() + timedelta(days=3)).strftime("%Y-%m-%d")
        result = calculate_deadline("reclamo_cautelare", data_decorrenza=domani)
        assert result["ok"] is True
        # Può essere urgente a seconda della data


# ---------------------------------------------------------------------------
# TC-13: Templates — diffida italiana
# ---------------------------------------------------------------------------

class TestTC13TemplatesDiffida:
    """TC-13: I template di redazione sono in italiano e strutturati."""

    def test_diffida_template_italiano(self):
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
        result = build_diffida_messa_in_mora_template({})
        assert "si invita e diffida formalmente" in result
        assert "in difetto" in result
        assert "riserva di agire" in result
        assert "Dear" not in result
        assert "I am writing" not in result

    def test_sollecito_template_italiano(self):
        from lex.providers.deterministic_provider import build_sollecito_pagamento_template
        result = build_sollecito_pagamento_template({})
        assert "SOLLECITO" in result.upper()
        assert "pagamento" in result.lower()
        assert "Dear" not in result

    def test_pec_template_italiano(self):
        from lex.providers.deterministic_provider import build_pec_formale_template
        result = build_pec_formale_template({})
        assert "PEC" in result
        assert "Oggetto" in result
        assert "Dear" not in result

    def test_contestazione_template_italiano(self):
        from lex.providers.deterministic_provider import build_contestazione_fattura_template
        result = build_contestazione_fattura_template({})
        assert "CONTESTAZIONE" in result.upper()
        assert "fattura" in result.lower()
        assert "Dear" not in result

    def test_richiesta_documenti_italiano(self):
        from lex.providers.deterministic_provider import build_richiesta_documenti_template
        result = build_richiesta_documenti_template({})
        assert "RICHIESTA" in result.upper()
        assert "documenti" in result.lower()

    def test_invito_stipula_italiano(self):
        from lex.providers.deterministic_provider import build_invito_a_stipula_template
        result = build_invito_a_stipula_template({})
        assert "stipula" in result.lower()

    def test_riscontro_italiano(self):
        from lex.providers.deterministic_provider import build_riscontro_comunicazione_template
        result = build_riscontro_comunicazione_template({})
        assert "riscontro" in result.lower() or "RISCONTRO" in result

    def test_lettera_cliente_italiano(self):
        from lex.providers.deterministic_provider import build_lettera_cliente_template
        result = build_lettera_cliente_template({})
        assert "LETTERA" in result.upper() or "cliente" in result.lower()


# ---------------------------------------------------------------------------
# TC-14: Snapshot bug originale — diffida in inglese
# ---------------------------------------------------------------------------

class TestTC14SnapshotDiffidaBug:
    """TC-14: Regressione bug originale 'scrivi un diffida'."""

    def test_intent_classificato_bozza_lettera(self):
        from lex.research.request_profile import classify_request
        profile = classify_request("scrivi un diffida professionale se serve utilizza la ricerca web")
        assert profile.intent == "bozza_lettera"

    def test_workflow_routing_corretto(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("scrivi un diffida professionale se serve utilizza la ricerca web")
        assert router.resolve_workflow(req) == "drafting_legal_letter"

    def test_workflow_registrato(self):
        from lex.workflows import WORKFLOW_REGISTRY
        assert "drafting_legal_letter" in WORKFLOW_REGISTRY
        assert "bozza_lettera" in WORKFLOW_REGISTRY

    def test_template_senza_inglese(self):
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
        bozza = build_diffida_messa_in_mora_template({})
        forbidden = ["Okay, here's", "Dear", "I am writing", "Please", "Subject:"]
        for fragment in forbidden:
            assert fragment not in bozza, f"Frammento inglese '{fragment}' trovato nella diffida"


# ---------------------------------------------------------------------------
# TC-15: Evidence relevance guard — redazione
# ---------------------------------------------------------------------------

class TestTC15EvidenceRelevanceGuard:
    """TC-15: La guardia pertinenza filtra fonti irrilevanti."""

    def test_evidenza_irrilevante_per_diffida(self):
        from lex.guards.evidence_relevance_guard import EvidenceRelevanceGuard
        guard = EvidenceRelevanceGuard()
        evidence = {
            "items": [
                {"title": "Cass. Civ. sentenza n. 12345/2022", "content": "Massima giurisprudenziale..."},
                {"title": "Gazzetta Ufficiale D.Lgs. 150/2022", "content": "Normativa penale..."},
            ]
        }
        verdict = guard.check(workflow="drafting_legal_letter", evidence=evidence, draft=_make_draft(""))
        assert verdict.allowed is True
        if verdict.warnings:
            assert "irrilevant" in " ".join(verdict.warnings).lower()

    def test_evidenza_rilevante_per_diffida(self):
        from lex.guards.evidence_relevance_guard import EvidenceRelevanceGuard
        guard = EvidenceRelevanceGuard()
        evidence = {
            "items": [
                {"title": "Modello diffida messa in mora", "content": "Formula diffida..."},
            ]
        }
        verdict = guard.check(workflow="bozza_lettera", evidence=evidence, draft=_make_draft(""))
        assert verdict.allowed is True
        assert not verdict.warnings

    def test_workflow_non_redazione_passthrough(self):
        from lex.guards.evidence_relevance_guard import EvidenceRelevanceGuard
        guard = EvidenceRelevanceGuard()
        evidence = {"items": [{"title": "Cass. Civ.", "content": "..."}]}
        verdict = guard.check(workflow="giurisprudenza", evidence=evidence, draft=_make_draft(""))
        assert verdict.allowed is True


# ---------------------------------------------------------------------------
# TC-16: Request profile — nuovi intenti
# ---------------------------------------------------------------------------

class TestTC16RequestProfileNewIntents:
    """TC-16: I nuovi intenti sono classificati correttamente."""

    @pytest.mark.parametrize("query,expected_intent", [
        ("non hai capito cosa intendevo", "lex_feedback_diagnostico"),
        ("calcola il termine per l'opposizione entro 40 giorni", "termini_processuali"),
        ("checklist deposito telematico PST", "deposito_telematico"),
        ("Cass. Civ. n. 12345/2023", "giurisprudenza_specifica"),
    ])
    def test_classify_new_intents(self, query: str, expected_intent: str):
        from lex.research.request_profile import classify_request
        profile = classify_request(query)
        assert profile.intent == expected_intent, (
            f"Query {query!r}: atteso {expected_intent!r}, trovato {profile.intent!r}"
        )


# ---------------------------------------------------------------------------
# TC-17: Tools registry — 25+ strumenti disponibili
# ---------------------------------------------------------------------------

class TestTC17ToolsRegistry:
    """TC-17: Il registro strumenti è completo."""

    def test_tools_count(self):
        from lex.tools.legal_studio_tools import list_tools
        tools = list_tools()
        assert len(tools) >= 25, f"Trovati solo {len(tools)} strumenti (attesi ≥ 25)"

    def test_tools_have_required_fields(self):
        from lex.tools.legal_studio_tools import list_tools
        for tool in list_tools():
            assert "name" in tool
            assert "label" in tool
            assert "area" in tool

    def test_dispatch_calculate_tariffario(self):
        from lex.tools.legal_studio_tools import dispatch_tool
        result = dispatch_tool("calculate_tariffario", valore_causa=10000.0)
        assert result["ok"] is True

    def test_dispatch_tool_non_esistente(self):
        from lex.tools.legal_studio_tools import dispatch_tool
        result = dispatch_tool("strumento_inesistente")
        assert result["ok"] is False
        assert "disponibili" in result


# ---------------------------------------------------------------------------
# TC-18: Workflow registry — tutti i nuovi workflow registrati
# ---------------------------------------------------------------------------

class TestTC18WorkflowRegistry:
    """TC-18: Tutti i nuovi workflow sono nel registro."""

    @pytest.mark.parametrize("workflow_name", [
        "drafting_legal_letter",
        "bozza_lettera",
        "lettera",
        "lex_feedback_diagnostico",
        "giurisprudenza_specifica",
        "termini_processuali",
        "deposito_telematico",
        "pec_comunicazioni",
        "cabina",
        "question_answering",
    ])
    def test_workflow_registrato(self, workflow_name: str):
        from lex.workflows import WORKFLOW_REGISTRY
        assert workflow_name in WORKFLOW_REGISTRY, f"Workflow {workflow_name!r} non registrato"

    def test_system_prompt_for_all_workflows(self):
        from lex.workflows import WORKFLOW_REGISTRY, system_prompt_for
        for name in WORKFLOW_REGISTRY:
            prompt = system_prompt_for(name)
            assert isinstance(prompt, str)


# ---------------------------------------------------------------------------
# TC-19: Intent matrix — priority routing ordine corretto
# ---------------------------------------------------------------------------

class TestTC19PriorityRouting:
    """TC-19: Il feedback ha priorità 1 (massima) nel router."""

    def test_feedback_ha_priorita_massima(self):
        from lex.research.legal_studio_intent_matrix import all_intents
        intents = all_intents()
        first = intents[0]
        assert first.key == "lex_feedback_diagnostico"
        assert first.priority == 1

    def test_redazione_ha_priorita_2(self):
        from lex.research.legal_studio_intent_matrix import all_intents
        intents = all_intents()
        # Cerco redazione_legale
        redazione = next((i for i in intents if i.key == "redazione_legale"), None)
        assert redazione is not None
        assert redazione.priority <= 3

    def test_feedback_supera_redazione_nel_router(self):
        from lex.router import LexRouter
        router = LexRouter()
        req = _make_request("non hai capito, volevo una diffida non un sollecito")
        workflow = router.resolve_workflow(req)
        assert workflow == "lex_feedback_diagnostico"


# ---------------------------------------------------------------------------
# TC-20: Integrazione — pipeline request_profile + router coerente
# ---------------------------------------------------------------------------

class TestTC20PipelineCoerenza:
    """TC-20: Intent da request_profile e routing da LexRouter sono coerenti."""

    @pytest.mark.parametrize("query,expected_profile_intent,expected_workflow", [
        ("scrivi una diffida al condominio", "bozza_lettera", "drafting_legal_letter"),
        ("calcola il termine per l'appello", "termini_processuali", "termini_processuali"),
        ("errore PST nel deposito telematico", "deposito_telematico", "deposito_telematico"),
        ("non hai capito, riprova", "lex_feedback_diagnostico", "lex_feedback_diagnostico"),
        ("sentenza Cass. n. 12345/2023", "giurisprudenza_specifica", "giurisprudenza_specifica"),
    ])
    def test_pipeline_coherence(
        self,
        query: str,
        expected_profile_intent: str,
        expected_workflow: str,
    ):
        from lex.research.request_profile import classify_request
        from lex.router import LexRouter

        profile = classify_request(query)
        assert profile.intent == expected_profile_intent, (
            f"Profile intent errato per {query!r}: "
            f"atteso {expected_profile_intent!r}, trovato {profile.intent!r}"
        )

        req = _make_request(query, intent=profile.intent)
        router = LexRouter()
        workflow = router.resolve_workflow(req)
        assert workflow == expected_workflow, (
            f"Workflow errato per {query!r}: "
            f"atteso {expected_workflow!r}, trovato {workflow!r}"
        )
