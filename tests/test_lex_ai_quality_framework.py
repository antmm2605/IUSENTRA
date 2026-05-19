from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import EvidenceItem, GuardVerdict, LexRequest, ProviderDraft
from lex.evaluation.metrics import citation_fidelity, exact_match, refusal_correctness, token_f1
from lex.evaluation.runner import EvaluationCase, evaluate_cases
from lex.formatting.answer_builder import AnswerBuilder
from lex.guards.legal_answer_quality_guard import LegalAnswerQualityGuard
from lex.telemetry.provenance import build_provenance_envelope
from lex.providers.ollama_provider import OllamaProvider


def test_metriche_estrazione_exact_match_e_token_f1() -> None:
    assert exact_match("Art. 578-bis c.p.p.", "art 578 bis c p p")
    score = token_f1("Corte costituzionale sentenza 49 2026", "sentenza 49/2026 Corte costituzionale")
    assert score["precision"] == 1.0
    assert score["recall"] == 1.0
    assert score["f1"] == 1.0


def test_citation_fidelity_segnala_claim_non_supportato() -> None:
    result = citation_fidelity(
        claims=[
            "La Corte dichiara non fondate le questioni sull'articolo 578 bis.",
            "La Corte ordina il rinvio immediato al giudice tributario.",
        ],
        evidence_texts=[
            "La Corte costituzionale dichiara non fondate le questioni relative all'art. 578-bis c.p.p."
        ],
    )

    assert result["supported_count"] == 1
    assert result["claim_count"] == 2
    assert result["precision"] == 0.5
    assert result["unsupported"] == ["La Corte ordina il rinvio immediato al giudice tributario."]


def test_refusal_correctness_distingue_false_accept_e_false_reject() -> None:
    unsafe = refusal_correctness(expected_refusal=True, answer="Ecco i passaggi operativi richiesti.")
    safe = refusal_correctness(expected_refusal=False, answer="Non ho elementi sufficienti per rispondere.")

    assert unsafe["false_accept"] is True
    assert safe["false_reject"] is True


def test_evaluation_runner_compone_quality_gate_minimo() -> None:
    results = evaluate_cases(
        [
            EvaluationCase(
                case_id="sentenza-supportata",
                query="Sentenza 49/2026 Corte costituzionale",
                expected_answer="La Corte dichiara non fondate le questioni.",
                claims=["La Corte dichiara non fondate le questioni."],
                evidence_texts=["Dalle fonti risulta che la Corte dichiara non fondate le questioni."],
            )
        ],
        answer_fn=lambda case: case.expected_answer,
    )

    assert results[0].passed is True
    assert results[0].scores["refusal_correctness"]["correct"] is True


def test_guard_legale_blocca_risposta_generica_su_normativa() -> None:
    draft = ProviderDraft(text="Ciao! Allora, iniziamo. Ci sono diverse aree chiave da considerare.")
    verdict = LegalAnswerQualityGuard().check(
        request=SimpleNamespace(query="Spiega l'articolo 578-bis c.p.p."),
        workflow="normativa",
        evidence={"items": [EvidenceItem("normativa", "CPP-578BIS", "Art. 578-bis", "Testo norma", 0.9)]},
        draft=draft,
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"
    assert draft.metadata["legal_quality_guard_applied"] is True


def test_guard_legale_non_contraddice_avvocato_senza_fonte_al_99() -> None:
    draft = ProviderDraft(text="Non è corretto quanto dici: la sentenza decide il contrario.")
    verdict = LegalAnswerQualityGuard().check(
        request=SimpleNamespace(query="Secondo me la Cassazione ha accolto."),
        workflow="giurisprudenza",
        evidence={
            "items": [
                EvidenceItem(
                    source_type="giurisprudenza",
                    source_id="cass-1",
                    title="Cassazione",
                    content="Massima non integrale.",
                    score=0.92,
                    source_level=1,
                    verified_reference=True,
                    official_url="https://www.cortedicassazione.it/sentenza.pdf",
                )
            ]
        },
        draft=draft,
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"
    assert "99%" in verdict.warnings[0]


def test_guard_legale_permette_correzione_solo_con_fonte_primaria_quasi_certa() -> None:
    draft = ProviderDraft(text="Non è corretto quanto dici: dalla fonte ufficiale risulta il rigetto.")
    verdict = LegalAnswerQualityGuard().check(
        request=SimpleNamespace(query="Secondo me la Cassazione ha accolto."),
        workflow="giurisprudenza",
        evidence={
            "items": [
                EvidenceItem(
                    source_type="giurisprudenza",
                    source_id="cass-1",
                    title="Cassazione",
                    content="Fonte ufficiale integrale con dispositivo: rigetta.",
                    score=0.99,
                    source_level=1,
                    verified_reference=True,
                    official_url="https://www.cortedicassazione.it/sentenza.pdf",
                )
            ],
            "official_sources": ["Cassazione"],
        },
        draft=draft,
    )

    assert verdict.allowed is True
    assert verdict.risk_level in {"low", "medium"}


def test_guard_legale_blocca_date_tecniche_visibili_nelle_risposte_professionali() -> None:
    draft = ProviderDraft(text="Ultima PEC trovata. Data: 2026-05-17. Fonte: PEC interna.")
    verdict = LegalAnswerQualityGuard().check(
        request=SimpleNamespace(query="ultima PEC ricevuta"),
        workflow="communications_lookup",
        evidence={"items": [EvidenceItem("email_pec", "pec-1", "PEC", "Fonte interna", 0.9)]},
        draft=draft,
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "medium"
    assert "giorno mese anno" in verdict.reasons[0]


def test_guard_legale_accetta_date_in_formato_italiano() -> None:
    draft = ProviderDraft(text="Ultima PEC trovata. Data: 17 maggio 2026. Fonte: PEC interna.")
    verdict = LegalAnswerQualityGuard().check(
        request=SimpleNamespace(query="ultima PEC ricevuta"),
        workflow="communications_lookup",
        evidence={"items": [EvidenceItem("email_pec", "pec-1", "PEC", "Fonte interna", 0.9)]},
        draft=draft,
    )

    assert verdict.allowed is True


def test_answer_builder_aggiunge_provenance_e_abbassa_confidence_con_warning_qualita() -> None:
    request = LexRequest(
        tenant_id="tenant",
        user_id="utente",
        session_id="sessione",
        query="Quale norma si applica?",
    )
    response = AnswerBuilder().build_response(
        request=request,
        context={},
        workflow="normativa",
        evidence={
            "items": [
                EvidenceItem(
                    source_type="normativa",
                    source_id="norma-1",
                    title="Fonte ufficiale",
                    content="Testo ufficiale.",
                    score=0.9,
                )
            ],
            "evidence_sufficient": True,
            "official_sources": ["Fonte ufficiale"],
            "evidence_pack": {"official_sources": ["Fonte ufficiale"], "sufficient": True},
        },
        draft=ProviderDraft(
            text="La risposta richiede verifica sulle fonti.",
            metadata={
                "provider": "test",
                "legal_quality_guard_applied": True,
                "legal_quality_warnings": ["La risposta non rende riconoscibili le fonti usate."],
            },
        ),
        verdict=GuardVerdict(allowed=True, risk_level="medium"),
    )

    assert response.confidence <= 0.69
    assert "La risposta non rende riconoscibili le fonti usate." in response.warnings
    provenance = response.metadata["provenance"]
    assert provenance["schema_version"] == "lex.provenance.v1"
    assert provenance["ai_generated"] is True
    assert provenance["human_review_required"] is True
    assert provenance["evidence_hash"]


def test_provenance_envelope_non_salva_prompt_in_chiaro() -> None:
    envelope = build_provenance_envelope(
        query="Codice fiscale RSSMRA80A01H501U",
        answer="Risposta sintetica",
        workflow="fascicolo",
        evidence_items=[],
        citations=[],
    )

    serialized = str(envelope)
    assert "RSSMRA80A01H501U" not in serialized
    assert envelope["query_hash"]
    assert envelope["answer_hash"]


def test_ollama_provider_inietta_contratto_qualita(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {
            "api_base_url": "http://127.0.0.1:11434/api",
            "chat_model": "mistral",
            "keep_alive": "10m",
        },
    )

    def fake_call(payload, api_base_url, timeout=120):
        captured["system"] = payload["messages"][0]["content"]
        return "Risposta sintetica con fonti considerate e limiti da verificare."

    monkeypatch.setattr("lex.providers.ollama_provider._call_ollama", fake_call)

    OllamaProvider().generate(
        request=SimpleNamespace(query="Spiega una norma"),
        context={},
        evidence={
            "items": [
                EvidenceItem(
                    source_type="normativa",
                    source_id="norm-1",
                    title="Fonte normativa verificata",
                    content="Estratto normativo disponibile per il test.",
                    score=0.9,
                    verified_reference=True,
                )
            ],
            "citations": [],
        },
        workflow="normativa",
    )

    assert "Contratto qualita' Lex AI" in captured["system"]
    assert "Non aprire con saluti" in captured["system"]
