from __future__ import annotations

from types import SimpleNamespace

from lex.contracts import Citation, LexResponse
from lex.http_bounded_bridge import build_bounded_http_payload


class DummyLexService:
    def __init__(self, response: LexResponse) -> None:
        self.response = response
        self.last_request = None

    def ask(self, request):
        self.last_request = request
        return self.response


def _studio_context(**overrides):
    payload = {
        "sources": [{"id": "prev-1", "title": "Preventivo corrente"}],
        "structured_context": {"fascicolo": {"id": "FAS-1"}},
        "focus_label": "preventivi",
        "focus_topic": "preventivi",
        "request_profile": {
            "intent": "preventivo_guidato",
            "source_mode": "balanced",
            "needs_external_validation": True,
            "drafting_mode": False,
        },
        "execution_policy": {"allow_web_fallback": True},
        "source_policy_summary": {"reasoning": "Base economica interna disponibile."},
        "source_mode": "balanced",
        "web_fallback_used": False,
        "web_execution_requested": False,
    }
    payload.update(overrides)
    return payload


def test_http_bridge_instrada_preventivo_sul_workflow_bounded(monkeypatch):
    response = LexResponse(
        answer="Possiamo partire dal preventivo guidato.",
        citations=[
            Citation(
                source_type="preventivo",
                source_id="prev-1",
                title="Preventivo guidato",
                excerpt="Workflow commerciale con dati minimi richiesti.",
                confidence=0.84,
            )
        ],
        confidence=0.84,
        answer_mode="grounded",
        metadata={"workflow": "economico", "provider": "deterministic"},
        evidence_summary={"official_count": 0, "trusted_count": 1, "fallback_triggered": False, "evidence_count": 1},
    )
    service = DummyLexService(response)
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="admin"),
        studio=SimpleNamespace(slug="antonella-mammola"),
        data={"session_id": "sess-1", "messages": [], "mode": "chat"},
        current_user_message="vorrei fare un preventivo",
        resolved_effective_question="vorrei fare un preventivo",
        studio_context=_studio_context(),
    )

    assert payload is not None
    assert payload["query_type"] == "workflow_answer"
    assert "preventivo guidato" in str(payload["answer"]).lower()
    assert payload["confidence_label"] == "alta"
    assert "base operativa di studio" in str(payload["confidence_reason"]).lower()
    assert service.last_request.intent == "evaluate_preventivo"
    assert service.last_request.workflow_hint == "economico"
    assert service.last_request.tenant_id == "antonella-mammola"


def test_http_bridge_non_aggiunge_fonti_legali_di_comodo_su_workflow_economico(monkeypatch):
    response = LexResponse(
        answer="Possiamo partire dal preventivo guidato.",
        citations=[],
        confidence=0.82,
        answer_mode="grounded",
        metadata={"workflow": "economico", "provider": "deterministic"},
        legal_basis=["Consiglio Nazionale Forense", "Gazzetta Ufficiale"],
        considered_sources=["Preventivo guidato"],
        evidence_summary={"official_count": 2, "trusted_count": 1, "fallback_triggered": False, "evidence_count": 1},
    )
    service = DummyLexService(response)
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="admin"),
        studio=SimpleNamespace(slug="antonella-mammola"),
        data={"session_id": "sess-1b", "messages": [], "mode": "chat"},
        current_user_message="vorrei fare un preventivo",
        resolved_effective_question="vorrei fare un preventivo",
        studio_context=_studio_context(),
    )

    assert payload is not None
    assert payload["sources"] == []


def test_http_bridge_attiva_ricerca_web_quando_manca_contesto_interno(monkeypatch):
    response = LexResponse(
        answer="Ho trovato una base normativa ufficiale sufficiente per partire.",
        citations=[],
        confidence=0.78,
        answer_mode="grounded",
        metadata={
            "workflow": "normativa",
            "provider": "ollama",
            "fallback_triggered": True,
        },
        evidence_summary={"official_count": 2, "trusted_count": 0, "fallback_triggered": True},
    )
    service = DummyLexService(response)
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="admin"),
        studio=SimpleNamespace(slug="antonella-mammola"),
        data={"session_id": "sess-2", "messages": [], "mode": "chat"},
        current_user_message="sentenza n. 8785 del 08/04/2026",
        resolved_effective_question="sentenza n. 8785 del 08/04/2026",
        studio_context=_studio_context(
            sources=[],
            structured_context={},
            focus_label="ricerca legale aggiornata",
            focus_topic="sentenze_web",
            request_profile={
                "intent": "giurisprudenza",
                "source_mode": "strict",
                "needs_external_validation": True,
                "drafting_mode": False,
            },
            source_mode="strict",
        ),
    )

    assert payload is not None
    assert payload["web_fallback_used"] is True
    assert service.last_request.allow_external_research is True
    assert service.last_request.require_official_sources is True
    assert service.last_request.require_citations is True
    assert service.last_request.workflow_hint == "giurisprudenza"


def test_http_bridge_propaga_badge_fonti_governate_partner_e_riservate(monkeypatch):
    response = LexResponse(
        answer="La fonte richiesta e governata ma richiede credenziali dedicate.",
        citations=[
            Citation(
                source_type="web_ufficiale",
                source_id="live-web-search:abc",
                title="Registro Imprese",
                excerpt="Accesso partner con credenziali.",
                confidence=0.71,
            )
        ],
        confidence=0.71,
        answer_mode="grounded",
        compared_sources=[
            {
                "title": "Registro Imprese",
                "source_registry_key": "registro_imprese_api",
                "source_access_status": "partner_api",
                "source_access_label": "Fonte partner con credenziali",
                "source_requires_credentials": True,
                "source_restricted": True,
            }
        ],
        metadata={
            "workflow": "normativa",
            "provider": "ollama",
            "partner_sources": [{"key": "registro_imprese_api"}],
            "restricted_sources": [{"key": "registro_imprese_api"}],
        },
        evidence_summary={"official_count": 1, "trusted_count": 0, "fallback_triggered": True},
    )
    service = DummyLexService(response)
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="admin"),
        studio=SimpleNamespace(slug="antonella-mammola"),
        data={"session_id": "sess-3", "messages": [], "mode": "chat"},
        current_user_message="Mi serve una visura dal registro imprese",
        resolved_effective_question="Mi serve una visura dal registro imprese",
        studio_context=_studio_context(
            sources=[],
            structured_context={},
            focus_label="ricerca legale aggiornata",
            focus_topic="sentenze_web",
            request_profile={
                "intent": "normativa",
                "source_mode": "strict",
                "needs_external_validation": True,
                "drafting_mode": False,
            },
            source_mode="strict",
        ),
    )

    assert payload is not None
    assert payload["sources"][0]["source_access_label"] == "Fonte partner con credenziali"
    assert payload["sources"][0]["source_requires_credentials"] is True
