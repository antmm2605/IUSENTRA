from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import LexResponse
from lex.http_bounded_bridge import build_bounded_http_payload


class DummyLexService:
    def __init__(self) -> None:
        self.last_request = None

    def ask(self, request):
        self.last_request = request
        return LexResponse(
            answer="Risposta governata.",
            confidence=0.62,
            answer_mode="needs_review",
            metadata={"workflow": request.workflow_hint or "question_answering", "provider": "deterministic"},
            warnings=["Risposta prudenziale."],
            next_actions=["Aggancia evidenze aggiuntive."],
            evidence_summary={"evidence_count": 1, "evidence_sufficient": False},
        )


def _base_context(**overrides):
    payload = {
        "sources": [],
        "structured_context": {},
        "focus_label": "",
        "focus_topic": "",
        "request_profile": {"intent": "", "source_mode": "balanced", "drafting_mode": False},
        "execution_policy": {},
        "source_policy_summary": {},
        "source_mode": "balanced",
        "web_fallback_used": False,
        "web_execution_requested": False,
    }
    payload.update(overrides)
    return payload


def _call(studio_context, monkeypatch, *, question="Che cosa devo fare oggi?", attachments=None):
    service = DummyLexService()
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)
    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="utente"),
        studio=SimpleNamespace(slug="studio"),
        data={"session_id": "sess"},
        current_user_message=question,
        resolved_effective_question=question,
        studio_context=studio_context,
        attachments=attachments,
    )
    return payload, service


def test_governed_only_instrada_richiesta_operativa_generica(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")

    payload, service = _call(_base_context(), monkeypatch)

    assert payload is not None
    assert service.last_request is not None
    assert service.last_request.intent == "ask_lex"


def test_governed_only_instrada_normativa_senza_focus_esplicito(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    context = _base_context(
        request_profile={"intent": "normativa", "source_mode": "strict", "drafting_mode": False},
        source_mode="strict",
    )

    payload, service = _call(context, monkeypatch, question="Qual e la norma applicabile?")

    assert payload is not None
    assert service.last_request.workflow_hint == "normativa"
    assert service.last_request.require_official_sources is True


def test_governed_only_instrada_giurisprudenza_strict(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    context = _base_context(
        request_profile={"intent": "giurisprudenza", "source_mode": "strict", "drafting_mode": False},
        source_mode="strict",
    )

    payload, service = _call(context, monkeypatch, question="Cassazione n. 1234/2024")

    assert payload is not None
    assert service.last_request.workflow_hint == "giurisprudenza"
    assert service.last_request.intent == "research_giurisprudenza"


def test_attachments_non_diventano_prompt_libero(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    attachment = {
        "id": "att-1",
        "name": "atto.txt",
        "mime_type": "text/plain",
        "text_excerpt": "Testo dell'atto caricato.",
        "size_bytes": 32,
    }

    payload, service = _call(_base_context(), monkeypatch, attachments=[attachment])

    assert payload is not None
    assert service.last_request is not None
    seed_sources = service.last_request.metadata["studio_context_seed"]["sources"]
    assert seed_sources
    assert seed_sources[0]["metadata"]["origin"] == "user_attachment"
    assert "Testo dell'atto caricato" in seed_sources[0]["excerpt"]
