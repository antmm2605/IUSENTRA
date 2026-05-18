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


def test_opzione_web_libero_e_manuale_non_passa_da_job(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    context = _base_context(
        sources=[{"title": "Fonte del contesto pagina", "excerpt": "Non deve entrare nel web libero."}],
        structured_context={"fascicolo": {"id": "fas-1"}},
        request_profile={"intent": "", "source_mode": "balanced", "drafting_mode": False},
        source_mode="balanced",
    )
    service = DummyLexService()
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="utente"),
        studio=SimpleNamespace(slug="studio"),
        data={"session_id": "sess", "free_web_enabled": True},
        current_user_message="Cerca sul web libero questione penale R.G. 9926/2026",
        resolved_effective_question="Cerca sul web libero questione penale R.G. 9926/2026",
        studio_context=context,
    )

    assert payload is not None
    assert service.last_request is not None
    assert service.last_request.metadata["free_web_enabled"] is True
    assert service.last_request.metadata["force_free_web_search"] is True
    assert service.last_request.metadata["public_web_forced"] is True
    assert service.last_request.metadata["source_mode"] == "free_web"
    assert service.last_request.metadata["studio_context_seed"]["sources"] == []
    assert service.last_request.metadata["studio_context_seed"]["structured_context"] == {}
    assert service.last_request.allow_external_research is True
    assert service.last_request.require_official_sources is False
    assert payload["warnings"] == []
    assert payload["next_actions"] == []
    assert payload["disable_exports"] is False
    assert payload["legal_reference_guard_active"] is False
    assert payload["free_web_saves_to_db"] is False
    assert payload["free_web_responsibility"] == "controllo_avvocato"
    assert payload["execution_policy"]["responsibility_scope"] == "controllo_avvocato"


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
