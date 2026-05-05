from __future__ import annotations

from types import SimpleNamespace

from flask import Flask, Response

from lex.tests.test_orchestrator import FakeRequestsOK, make_orchestrator


def _sse_body(response: Response) -> str:
    return "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk) for chunk in response.response)


def _prepare(monkeypatch):
    orch = make_orchestrator(FakeRequestsOK())
    monkeypatch.setattr(orch.auth_guard, "ensure_can_access", lambda **kwargs: None)
    monkeypatch.setattr(
        "lex.orchestrator.resolve_current_and_previous_user_messages",
        lambda explicit_question, messages: ("spiegami questa questione", "", []),
    )
    monkeypatch.setattr("lex.orchestrator_http.build_bounded_http_payload", lambda **kwargs: None)
    return orch


class ExplodingLLM:
    def build_chat_payload(self, **kwargs):
        raise AssertionError("La chat libera non deve essere chiamata")

    def stream_chat(self, **kwargs):
        raise AssertionError("La chat libera non deve essere chiamata")


class StreamingLLM:
    called = False

    def build_chat_payload(self, **kwargs):
        self.called = True
        return {"messages": []}

    def stream_chat(self, **kwargs):
        def generate():
            yield 'data: {"token": "ok"}\n\n'
            yield "data: [DONE]\n\n"

        return generate


def test_raw_chat_bloccata_quando_env_non_attivo(monkeypatch):
    monkeypatch.delenv("LEX_RAW_CHAT_ENABLED", raising=False)
    orch = _prepare(monkeypatch)
    orch.llm_provider = ExplodingLLM()
    app = Flask(__name__)

    with app.test_request_context("/api/assistente/chat", method="POST"):
        response = orch.chat_response(user=None, studio=None, data={"messages": [{"role": "user", "content": "test"}]})

    body = _sse_body(response)
    assert "chat libera senza evidenze governate" in body
    assert "[DONE]" in body


def test_raw_chat_bloccata_se_env_attivo_ma_manca_flag_richiesta(monkeypatch):
    monkeypatch.setenv("LEX_RAW_CHAT_ENABLED", "1")
    orch = _prepare(monkeypatch)
    orch.llm_provider = ExplodingLLM()
    app = Flask(__name__)

    with app.test_request_context("/api/assistente/chat", method="POST"):
        response = orch.chat_response(user=None, studio=None, data={"messages": [{"role": "user", "content": "test"}]})

    assert "chat libera senza evidenze governate" in _sse_body(response)


def test_raw_chat_passa_solo_con_env_e_flag_esplicito(monkeypatch):
    monkeypatch.setenv("LEX_RAW_CHAT_ENABLED", "1")
    orch = _prepare(monkeypatch)
    provider = StreamingLLM()
    orch.llm_provider = provider
    app = Flask(__name__)

    with app.test_request_context("/api/assistente/chat", method="POST"):
        response = orch.chat_response(
            user=None,
            studio=None,
            data={
                "messages": [{"role": "user", "content": "test"}],
                "allow_unbounded_generation": True,
            },
        )

    body = _sse_body(response)
    assert provider.called is True
    assert '"ok"' in body
