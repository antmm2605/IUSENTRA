from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest
from lex.guards.case_law_answer_guard import CaseLawAnswerGuard
from lex.http_bounded_bridge import _should_use_bounded_workflow
from lex.reasoning.case_law_interpreter import (
    build_case_law_prompt_block,
    build_deterministic_case_law_answer,
)
from lex.providers.ollama_provider import OllamaProvider
from lex.router import LexRouter


def test_router_detects_corte_costituzionale_sentence():
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="utente",
        session_id="s1",
        query="Sentenza n. 49/2026 - Corte costituzionale",
    )

    # Sentenza con numero esatto → giurisprudenza_specifica (ricerca su fonti ufficiali)
    assert LexRouter().resolve_workflow(request) == "giurisprudenza_specifica"


def test_http_bridge_allows_bounded_giurisprudenza():
    studio_context = {
        "source_mode": "strict",
        "focus_topic": "archivio_sentenze",
        "web_execution_requested": False,
        "request_profile": {
            "intent": "giurisprudenza",
            "source_mode": "strict",
            "drafting_mode": False,
        },
    }

    assert _should_use_bounded_workflow(attachments=None, studio_context=studio_context) is True


def test_case_law_interpreter_extracts_dispositivo():
    item = EvidenceItem(
        source_type="giurisprudenza",
        source_id="corte-cost-49-2026",
        title="Sentenza n. 49/2026 - Corte costituzionale",
        content="La questione riguarda l'art. 578-bis c.p.p.",
        score=0.92,
        metadata={
            "organo": "Corte costituzionale",
            "numero": "49",
            "anno": "2026",
            "norme_citate": ["art. 578-bis c.p.p."],
            "dispositivo": "dichiara non fondate le questioni sollevate",
            "url_pagina_ufficiale": "https://www.cortecostituzionale.it/",
        },
        verified_reference=True,
        official_url="https://www.cortecostituzionale.it/",
    )

    block = build_case_law_prompt_block([item])

    assert "Sentenza n. 49/2026" in block
    assert "dichiara non fondate" in block
    assert "art. 578-bis c.p.p." in block


def test_case_law_guard_rejects_generic_answer():
    answer = "Ciao! Allora, iniziamo. Il fascicolo e' in fase di analisi..."

    allowed, warnings = CaseLawAnswerGuard().evaluate(answer, evidence_items=[{"title": "Sentenza"}])

    assert allowed is False
    assert warnings


def test_deterministic_case_law_answer_contains_required_sections():
    answer = build_deterministic_case_law_answer(
        [
            {
                "title": "Sentenza n. 49/2026 - Corte costituzionale",
                "content": "Questione relativa all'art. 578-bis c.p.p.",
                "metadata": {
                    "organo": "Corte costituzionale",
                    "dispositivo": "dichiara non fondate le questioni",
                    "principio_sintetico": "Il giudice deve attenersi ai limiti indicati dalla pronuncia.",
                    "url_pagina_ufficiale": "https://www.cortecostituzionale.it/",
                },
            }
        ]
    )

    assert "Pronuncia individuata" in answer
    assert "Oggetto della decisione" in answer
    assert "Decisione / dispositivo" in answer
    assert "Principio ricavabile" in answer
    assert "Limiti" in answer
    assert "Fonti considerate" in answer


def test_ollama_provider_replaces_generic_case_law_answer(monkeypatch):
    monkeypatch.setattr(
        "lex.providers.ollama_provider._call_ollama",
        lambda *args, **kwargs: "Ciao! Allora, iniziamo. Il fascicolo e' in fase di analisi...",
    )
    request = LexRequest(
        tenant_id="tenant-test",
        user_id="utente",
        session_id="s1",
        query="Sentenza n. 49/2026 - Corte costituzionale",
    )
    evidence = {
        "items": [
            EvidenceItem(
                source_type="giurisprudenza",
                source_id="corte-cost-49-2026",
                title="Sentenza n. 49/2026 - Corte costituzionale",
                content="Questione relativa all'art. 578-bis c.p.p.",
                score=0.92,
                metadata={
                    "organo": "Corte costituzionale",
                    "dispositivo": "dichiara non fondate le questioni",
                    "principio_sintetico": "Principio disponibile solo come estratto.",
                },
            )
        ]
    }

    draft = OllamaProvider().generate(request, context={}, evidence=evidence, workflow="giurisprudenza")

    assert "Pronuncia individuata" in draft.text
    assert "Decisione / dispositivo" in draft.text
    assert draft.metadata["case_law_fallback_used"] is True
