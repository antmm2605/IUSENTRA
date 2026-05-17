"""Test suite per il fix Lex Drafting Intent / Language Bug.

Verifica 16 scenari chiave:
- Routing corretto bozza_lettera → drafting_legal_letter
- Nessuna risposta in inglese per diffida/messa in mora
- Fallback deterministico italiano
- Guard linguistica pipeline
- Patterns request_profile
- Web search non attivata per generic drafting
- Follow-up resolver italiano
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------

def _make_request(query: str, intent: str = "", workflow_hint: str = "", fascicolo_id: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        query=query,
        intent=intent,
        workflow_hint=workflow_hint,
        fascicolo_id=fascicolo_id,
        metadata={},
    )


# ---------------------------------------------------------------------------
# Test 1–4: LexRouter routing
# ---------------------------------------------------------------------------

class TestLexRouterDiffidaRouting:
    """Il router deve instradare qualsiasi richiesta di diffida/lettera verso drafting_legal_letter."""

    def test_intent_bozza_lettera_routes_to_drafting_legal_letter(self):
        from lex.router import LexRouter
        router = LexRouter()
        request = _make_request("scrivi una diffida", intent="bozza_lettera")
        assert router.resolve_workflow(request) == "drafting_legal_letter"

    def test_text_hint_diffida_routes_to_drafting_legal_letter(self):
        from lex.router import LexRouter
        router = LexRouter()
        request = _make_request("scrivi un diffida professionale se serve utilizza la ricerca web")
        assert router.resolve_workflow(request) == "drafting_legal_letter"

    def test_text_hint_messa_in_mora_routes_to_drafting_legal_letter(self):
        from lex.router import LexRouter
        router = LexRouter()
        request = _make_request("ho bisogno di una messa in mora per il mio cliente")
        assert router.resolve_workflow(request) == "drafting_legal_letter"

    def test_text_hint_sollecito_formale_routes_to_drafting_legal_letter(self):
        from lex.router import LexRouter
        router = LexRouter()
        request = _make_request("redigi un sollecito formale di pagamento")
        assert router.resolve_workflow(request) == "drafting_legal_letter"


# ---------------------------------------------------------------------------
# Test 5–6: WorkflowRegistry
# ---------------------------------------------------------------------------

class TestWorkflowRegistry:
    """LetteraWorkflow deve essere registrato e avere system prompt in italiano."""

    def test_drafting_legal_letter_in_registry(self):
        from lex.workflows import WORKFLOW_REGISTRY
        assert "drafting_legal_letter" in WORKFLOW_REGISTRY

    def test_lettera_workflow_system_prompt_is_italian(self):
        from lex.workflows import system_prompt_for
        prompt = system_prompt_for("drafting_legal_letter")
        assert len(prompt) > 100
        assert "italiano" in prompt.lower() or "italiana" in prompt.lower()
        assert "diffida" in prompt.lower()
        # Il prompt cita "Dear" come formula VIETATA — verifica che non inizi con un saluto inglese
        assert not prompt.lstrip().startswith("Dear")
        assert "Sei il modulo" in prompt or "sei il modulo" in prompt.lower()


# ---------------------------------------------------------------------------
# Test 7–9: ItalianResponseGuard detection
# ---------------------------------------------------------------------------

class TestItalianResponseGuard:
    """La guardia deve rilevare e riscrivere/bloccare risposte inglesi."""

    def test_english_email_detected(self):
        from lex.guards.italian_response_guard import detect_non_italian_response
        english_text = (
            "Okay, here's a draft of a professional-sounding email for a formal demand letter. "
            "Dear Recipient, I am writing to formally notify you that the payment due remains outstanding. "
            "Please be advised that failure to comply with this demand within 15 days will result in legal action."
        )
        assert detect_non_italian_response(english_text) is True

    def test_italian_diffida_not_detected_as_english(self):
        from lex.guards.italian_response_guard import detect_non_italian_response
        italian_text = (
            "DIFFIDA E MESSA IN MORA\n\n"
            "Con la presente si invita e diffida formalmente la S.V. ad adempiere entro 15 giorni. "
            "In difetto, ci si riserva di agire in ogni sede competente con ogni conseguenza di legge."
        )
        assert detect_non_italian_response(italian_text) is False

    def test_rewrite_replaces_english_phrases(self):
        from lex.guards.italian_response_guard import rewrite_or_reject_non_italian_response
        text = "Okay, here's a draft of the letter. Dear Sir, I am writing to formally notify you."
        result = rewrite_or_reject_non_italian_response(text, {"workflow": "drafting_legal_letter"})
        assert "Okay, here's" not in result
        assert "Dear Sir" not in result


# ---------------------------------------------------------------------------
# Test 10–11: ItalianLanguageGuard pipeline integration
# ---------------------------------------------------------------------------

class TestItalianLanguageGuardPipeline:
    """ItalianLanguageGuard deve essere nella pipeline post-guard dell'orchestratore."""

    def test_italian_language_guard_in_post_guards(self):
        from lex.guards.orchestrator import GuardOrchestrator
        from lex.guards.italian_language_guard import ItalianLanguageGuard
        orchestrator = GuardOrchestrator()
        guard_types = [type(g) for g in orchestrator.post_guards]
        assert ItalianLanguageGuard in guard_types

    def test_italian_language_guard_blocks_english_draft(self):
        from lex.guards.italian_language_guard import ItalianLanguageGuard
        guard = ItalianLanguageGuard()
        english_draft = SimpleNamespace(
            text=(
                "Okay, here's a draft of a professional email. Dear Recipient, "
                "I am writing to formally notify you that your payment is overdue. "
                "Please be advised that failure to comply with this demand will result "
                "in legal action being taken against you. Sincerely yours."
            ),
            metadata={},
        )
        request = _make_request("scrivi un diffida", intent="bozza_lettera")
        verdict = guard.check(
            request=request,
            context={},
            workflow="drafting_legal_letter",
            evidence={},
            draft=english_draft,
        )
        # Deve bloccare (allowed=False) o riscrivere (rewritten_draft != None)
        assert not verdict.allowed or verdict.rewritten_draft is not None


# ---------------------------------------------------------------------------
# Test 12: Request profile classification
# ---------------------------------------------------------------------------

class TestRequestProfileDiffida:
    """Il profilo deve classificare le varianti di diffida come bozza_lettera."""

    @pytest.mark.parametrize("query", [
        "scrivi un diffida professionale",
        "messa in mora per un cliente",
        "prepara una diffida formale",
        "redigi un sollecito formale",
        "ho bisogno di una lettera di diffida",
        "costituzione in mora per mancato pagamento",
    ])
    def test_diffida_classified_as_bozza_lettera(self, query: str):
        from lex.research.request_profile import classify_request
        profile = classify_request(query)
        assert profile.intent == "bozza_lettera", (
            f"Query '{query}' classificata come '{profile.intent}' invece di 'bozza_lettera'"
        )


# ---------------------------------------------------------------------------
# Test 13: Deterministic fallback template
# ---------------------------------------------------------------------------

class TestDiffidaTemplate:
    """build_diffida_messa_in_mora_template deve produrre testo italiano valido."""

    def test_template_is_italian(self):
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
        from lex.guards.italian_response_guard import detect_non_italian_response
        result = build_diffida_messa_in_mora_template({})
        assert detect_non_italian_response(result) is False

    def test_template_contains_required_phrases(self):
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
        result = build_diffida_messa_in_mora_template({})
        required = [
            "diffida",
            "messa in mora",
            "si invita e diffida formalmente",
            "in difetto",
            "riserva di agire",
            "Dati da completare",
        ]
        for phrase in required:
            assert phrase.lower() in result.lower(), f"Frase obbligatoria mancante: '{phrase}'"

    def test_template_never_contains_english(self):
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
        result = build_diffida_messa_in_mora_template({})
        forbidden = ["Dear", "Okay, here", "I am writing", "Please", "Sincerely"]
        for phrase in forbidden:
            assert phrase not in result, f"Frase inglese trovata nel template: '{phrase}'"

    def test_template_checklist_non_usa_blocco_citazione(self):
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template

        result = build_diffida_messa_in_mora_template({})

        assert "\n\n**Dati da completare prima dell'invio**\n\n" in result
        assert "\n- Nome e dati completi del cliente mittente" in result
        assert "\n> - " not in result
        assert "> **Dati da completare" not in result

    def test_flat_diffida_viene_impaginata_come_documento(self):
        from lex.formatting.answer_builder import AnswerBuilder

        flat = (
            "BOZZA — DIFFIDA E MESSA IN MORA "
            "Studio Legale Montagnese Avv. Roberto Montagnese Via NINO BIXIO 4, Taurianova, RC "
            "C.F. MNTRRT64L01063H - P.IVA 01301790802 Tel. +393474940097 - "
            "Email r.montagnese@tiscali.it - PEC roberto.montagnese@coapalmi.legalmail.it "
            "17/05/2026 Spett.le [Nome e Cognome / Ragione sociale della controparte] "
            "[Indirizzo, CAP, Città, Provincia] Oggetto: DIFFIDA E MESSA IN MORA — "
            "[descrizione del credito/obbligo inademputo] Con la presente, il sottoscritto/la sottoscritta "
            "Avv. Roberto Montagnese, in qualità di difensore di [Nome del cliente - da completare], "
            "si invita e diffida formalmente la S.V. / codesta Spettabile Società ad adempiere. "
            "Fatto [Esporre in modo sintetico e cronologico i fatti rilevanti — DA COMPLETARE] "
            "Diritto Ai sensi dell'art. 1219 c.c., la presente lettera costituisce formale messa in mora. "
            "Richiesta formale Si diffida la S.V. a: 1. [Prima richiesta specifica — DA COMPLETARE] "
            "2. [Eventuale seconda richiesta — DA COMPLETARE] Avvertenza in difetto di riscontro positivo "
            "nel termine indicato, il sottoscritto si riserva di agire. Con osservanza, Avv. Roberto Montagnese "
            "Dati da completare prima dell'invio: > - Nome e dati completi del cliente mittente "
            "> - Dati completi della controparte (CF/PI se società) > - Importo esatto"
        )

        response = AnswerBuilder()._build_drafting_letter_response(
            request=_make_request("scrivi diffida"),
            draft=SimpleNamespace(text=flat, metadata={"provider": "test"}),
            verdict=SimpleNamespace(warnings=[], risk_level="medium"),
            confidence=0.72,
        )

        answer = response.answer
        assert answer.startswith("**BOZZA — DIFFIDA E MESSA IN MORA**\n\n---\n\n")
        assert "\n\n**Spett.le**\n" in answer
        assert "\n[Indirizzo, CAP, Città, Provincia]" in answer
        assert "\n\n**Oggetto:** DIFFIDA E MESSA IN MORA" in answer
        assert "\n\n**Fatto**\n\n" in answer
        assert "\n\n**Diritto**\n\n" in answer
        assert "\n\n**Richiesta formale**\n\n" in answer
        assert "\n1. [Prima richiesta specifica" in answer
        assert "\n2. [Eventuale seconda richiesta" in answer
        assert "\n\n**Avvertenza**\n\n" in answer
        assert "\n\n**Dati da completare prima dell'invio**\n\n" in answer
        assert "\n- Nome e dati completi del cliente mittente" in answer
        assert "\n> - " not in answer


# ---------------------------------------------------------------------------
# Test 14: Snapshot — il bug originale non può ripresentarsi
# ---------------------------------------------------------------------------

class TestSnapshotOriginalBug:
    """Snapshot test: l'input esatto del bug deve produrre output italiano."""

    def test_diffida_query_snapshot_router(self):
        """Router: 'scrivi un diffida professionale se serve utilizza la ricerca web'
        deve produrre 'drafting_legal_letter', non 'question_answering'.
        """
        from lex.router import LexRouter
        router = LexRouter()
        request = _make_request(
            "scrivi un diffida professionale se serve utilizza la ricerca web"
        )
        workflow = router.resolve_workflow(request)
        assert workflow == "drafting_legal_letter", (
            f"BUG REGRESSIONE: workflow='{workflow}', atteso 'drafting_legal_letter'"
        )

    def test_diffida_query_snapshot_profile(self):
        """Request profile: l'input esatto del bug deve classificare come bozza_lettera."""
        from lex.research.request_profile import classify_request
        profile = classify_request(
            "scrivi un diffida professionale se serve utilizza la ricerca web"
        )
        assert profile.intent == "bozza_lettera", (
            f"BUG REGRESSIONE: intent='{profile.intent}', atteso 'bozza_lettera'"
        )

    def test_fallback_template_not_english(self):
        """Il fallback deterministico non deve mai produrre 'Okay, here's' o formule inglesi."""
        from lex.providers.deterministic_provider import build_diffida_messa_in_mora_template
        result = build_diffida_messa_in_mora_template({})
        assert "Okay, here's" not in result
        assert "here's a draft" not in result.lower()
        assert "Dear" not in result


# ---------------------------------------------------------------------------
# Test 15: Web search non attivata per bozza generica
# ---------------------------------------------------------------------------

class TestWebSearchNotTriggeredForDrafting:
    """Per bozza_lettera, 'web'/'cerca' nella query non deve attivare external search."""

    def test_generic_web_token_no_external_reason_for_drafting(self):
        from lex.http_bounded_bridge import _external_sources_reason
        reason = _external_sources_reason(
            "scrivi un diffida professionale se serve utilizza la ricerca web",
            studio_context={},
            request_profile={"intent": "bozza_lettera"},
            fascicolo_first=False,
        )
        assert reason is None, (
            f"External search attivata indebitamente per bozza generica: '{reason}'"
        )

    def test_normative_token_triggers_external_for_drafting(self):
        from lex.http_bounded_bridge import _external_sources_reason
        reason = _external_sources_reason(
            "scrivi un diffida con riferimento all'art. 1219 del codice civile",
            studio_context={},
            request_profile={"intent": "bozza_lettera"},
            fascicolo_first=False,
        )
        assert reason is not None


# ---------------------------------------------------------------------------
# Test 16: EvidenceRelevanceGuard
# ---------------------------------------------------------------------------

class TestEvidenceRelevanceGuard:
    """Il guard deve segnalare evidenze irrilevanti per il workflow di redazione."""

    def test_irrelevant_sentenze_flagged_for_drafting(self):
        from lex.guards.evidence_relevance_guard import EvidenceRelevanceGuard
        guard = EvidenceRelevanceGuard()
        evidence = {
            "items": [
                {"title": "Sentenza n. 1234/2023 Cass. Civ.", "excerpt": "massima giurisprudenziale"},
                {"title": "TAR Lazio n. 567/2022", "excerpt": "provvedimento amministrativo"},
            ]
        }
        verdict = guard.check(
            request=_make_request("scrivi una diffida"),
            context={},
            workflow="drafting_legal_letter",
            evidence=evidence,
            draft=SimpleNamespace(text="", metadata={}),
        )
        assert verdict.allowed is True
        assert len(verdict.warnings) > 0

    def test_non_drafting_workflow_not_affected(self):
        from lex.guards.evidence_relevance_guard import EvidenceRelevanceGuard
        guard = EvidenceRelevanceGuard()
        evidence = {
            "items": [
                {"title": "Sentenza n. 1234/2023 Cass. Civ.", "excerpt": "massima giurisprudenziale"},
            ]
        }
        verdict = guard.check(
            request=_make_request("ricerca giurisprudenza"),
            context={},
            workflow="giurisprudenza",
            evidence=evidence,
            draft=SimpleNamespace(text="", metadata={}),
        )
        assert verdict.allowed is True
        assert len(verdict.warnings) == 0
