"""Test locali del service Lex."""

from __future__ import annotations

from lex.guards.grounding import GroundingGuard
from lex.contracts import LexRequest
from lex.service import LexService


class DummyOrchestrator:
    def status_payload(self):
        return {"ok": True, "source": "dummy"}, 200

    def attachments_response(self, *, files):
        return {"ok": True, "attachments": files, "errors": [], "prompt_block": "BLOCK"}, 200


class DummyApplicationOrchestrator:
    def run(self, request):
        return {"answer": f"ok:{request.query}", "tenant": request.tenant_id}


def test_grounding_guard_marks_low_confidence_without_sources():
    result = GroundingGuard().evaluate(sources=[])

    assert result.grounded is False
    assert result.confidence == 0.1


def test_service_stato_uses_orchestrator(monkeypatch):
    service = LexService(dependency_factory=lambda: None)

    monkeypatch.setattr(service, "_orchestrator", lambda: DummyOrchestrator())

    payload, status = service.stato()

    assert status == 200
    assert payload == {"ok": True, "source": "dummy"}


def test_service_attachments_uses_orchestrator(monkeypatch):
    service = LexService(dependency_factory=lambda: None)

    monkeypatch.setattr(service, "_orchestrator", lambda: DummyOrchestrator())

    payload, status = service.attachments(files=[{"name": "atto.pdf"}])

    assert status == 200
    assert payload["ok"] is True
    assert payload["attachments"] == [{"name": "atto.pdf"}]
    assert payload["prompt_block"] == "BLOCK"


def test_service_ask_uses_application_orchestrator():
    service = LexService(orchestrator=DummyApplicationOrchestrator())

    result = service.ask(
        LexRequest(
            tenant_id="studio-test",
            user_id="admin",
            session_id="sess-1",
            query="riepilogo fascicolo",
        )
    )

    assert result == {"answer": "ok:riepilogo fascicolo", "tenant": "studio-test"}
