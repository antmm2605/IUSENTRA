from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, Response

from lex.dependencies import LexDependencies
from lex.orchestrator import LexOrchestrator


class FakeRequestsOK:
    class exceptions:
        class ConnectionError(Exception):
            pass

    @staticmethod
    def get(url, timeout=3):
        class Resp:
            @staticmethod
            def json():
                return {"models": [{"name": "mistral"}, {"name": "llama3"}]}

        return Resp()


class FakeRequestsDown:
    class exceptions:
        class ConnectionError(Exception):
            pass

    @staticmethod
    def get(url, timeout=3):
        raise FakeRequestsDown.exceptions.ConnectionError("down")


def make_deps(requests_module):
    return LexDependencies(
        requests_module=requests_module,
        build_studio_context=lambda **kwargs: {
            "sources": [],
            "citations": [],
            "prompt_block": "",
            "effective_question": kwargs.get("question", ""),
            "structured_context": {},
            "engine_ids": [],
            "source_ids": [],
            "execution_policy": {},
            "verified_legal_references": [],
            "research_strategy": "",
            "focus_topic": "",
            "focus_label": "",
            "competence_labels": [],
            "web_fallback_used": False,
            "web_execution_requested": False,
            "legal_reference_guard_active": False,
        },
        warm_studio_context=lambda **kwargs: {"sources": [{"id": "s1"}, {"id": "s2"}]},
        build_today_summary=lambda **kwargs: {},
        build_language_guidance=lambda **kwargs: SimpleNamespace(
            opening_line="",
            prompt_block="",
            mode="general",
        ),
        build_prompt=lambda **kwargs: "PROMPT DI TEST",
        resolve_followup_query=lambda *args, **kwargs: SimpleNamespace(
            effective_query=args[0] if args else "",
            reused_previous_topic=False,
            previous_user_text="",
            is_web_request=False,
            needs_web_search=False,
        ),
        resolve_social_and_operational_intent=lambda *args, **kwargs: SimpleNamespace(
            is_social_only=False,
            is_social_with_request=False,
            social_kind="",
            social_prefix="",
            effective_query=args[0] if args else "",
            raw_text=args[0] if args else "",
            is_daily_overview=False,
            is_followup=False,
            reused_previous_topic=False,
        ),
        latest_user_message=lambda *args, **kwargs: "",
        build_social_only_reply=lambda *args, **kwargs: "Dimmi pure.",
        resolved_runtime=lambda: {
            "api_base_url": "http://localhost:11434/api",
            "base_url": "http://localhost:11434",
            "chat_model": "mistral",
        },
        warm_runtime=lambda: {"ok": True, "chat_model": "mistral"},
        build_unverified_pdf_reply=lambda *args, **kwargs: "",
        build_docx_bytes=lambda **kwargs: b"DOCX-CONTENT",
        build_export_filename=lambda title, ext: f"{title}.{ext}",
        infer_export_title=lambda **kwargs: "Export Lex",
        build_attachment_prompt_block=lambda attachments: f"ALLEGATI:{len(attachments)}",
        parse_attachment_payloads=lambda files: (files, []),
    )


def make_orchestrator(requests_module=FakeRequestsOK()):
    return LexOrchestrator(make_deps(requests_module))


def test_status_payload_ok():
    orch = make_orchestrator(FakeRequestsOK())

    payload, status = orch.status_payload()

    assert status == 200
    assert payload["ok"] is True
    assert payload["url"] == "http://localhost:11434"
    assert payload["modello_attivo"] == "mistral"
    assert payload["modelli"] == ["mistral", "llama3"]


def test_status_payload_when_ollama_is_unreachable():
    orch = make_orchestrator(FakeRequestsDown())

    payload, status = orch.status_payload()

    assert status == 200
    assert payload["ok"] is False
    assert payload["errore"] == "Ollama non raggiungibile"
    assert payload["modelli"] == []


def test_warmup_response_returns_sources_ready_and_runtime():
    orch = make_orchestrator()

    payload, status = orch.warmup_response(
        question="Riepilogo fascicolo",
        context_label="fascicolo",
    )

    assert status == 200
    assert payload["ok"] is True
    assert payload["prewarmed"] is True
    assert payload["sources_ready"] == 2
    assert payload["runtime"] == {"ok": True, "chat_model": "mistral"}


def test_attachments_response_returns_prompt_block():
    orch = make_orchestrator()

    payload, status = orch.attachments_response(
        files=[{"name": "atto.pdf"}, {"name": "allegato.pdf"}]
    )

    assert status == 200
    assert payload["ok"] is True
    assert payload["attachments"] == [{"name": "atto.pdf"}, {"name": "allegato.pdf"}]
    assert payload["errors"] == []
    assert payload["prompt_block"] == "ALLEGATI:2"


def test_document_response_rejects_missing_answer():
    orch = make_orchestrator()

    payload, status = orch.document_response(data={})

    assert status == 400
    assert payload == {"ok": False, "errore": "Contenuto del documento mancante."}


def test_build_context_response_rejects_missing_question(monkeypatch):
    orch = make_orchestrator()

    monkeypatch.setattr(
        orch.auth_guard,
        "ensure_can_access",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        "lex.orchestrator.resolve_current_and_previous_user_messages",
        lambda explicit_question, messages: ("", "", []),
    )

    payload, status = orch.build_context_response(
        user=None,
        studio=None,
        data={},
    )

    assert status == 200
    assert payload["ok"] is False
    assert payload["errore"] == "Domanda mancante."
    assert payload["prompt"] == ""
    assert payload["sources"] == []
    assert payload["citations"] == []


def test_chat_response_social_only_returns_sse(monkeypatch):
    orch = make_orchestrator()

    monkeypatch.setattr(
        orch.auth_guard,
        "ensure_can_access",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        "lex.orchestrator.resolve_current_and_previous_user_messages",
        lambda explicit_question, messages: ("ciao", "", []),
    )

    orch.dependencies.resolve_social_and_operational_intent = lambda *args, **kwargs: SimpleNamespace(
        is_social_only=True,
        is_social_with_request=False,
        social_kind="greeting",
        social_prefix="",
        effective_query="ciao",
        raw_text="ciao",
        is_daily_overview=False,
        is_followup=False,
        reused_previous_topic=False,
    )

    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.test_request_context("/api/assistente/chat", method="POST"):
        response = orch.chat_response(
            user=None,
            studio=None,
            data={"messages": [{"role": "user", "content": "ciao"}]},
        )

    assert isinstance(response, Response)
    assert response.mimetype == "text/event-stream"

    body = "".join(
        chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk)
        for chunk in response.response
    )
    assert "Dimmi pure." in body
    assert "[DONE]" in body
