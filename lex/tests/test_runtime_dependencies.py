from __future__ import annotations

from flask import Flask, g

import lex.runtime_dependencies as runtime_dependencies


class _FakeRequests:
    class exceptions:
        class ConnectionError(Exception):
            pass


def _stub_dict(*args, **kwargs):
    return {}


def _stub_str(*args, **kwargs):
    return "ok"


def _stub_bytes(*args, **kwargs):
    return b"docx"


def _stub_tuple(*args, **kwargs):
    return ([], [])


def test_build_runtime_lex_dependencies_usa_i_binding_del_modulo(monkeypatch):
    monkeypatch.setattr(runtime_dependencies, "requests", _FakeRequests())
    monkeypatch.setattr(runtime_dependencies, "build_lex_studio_context", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "warm_lex_studio_context", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "build_today_operational_summary", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "build_language_guidance", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "build_assistente_prompt", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "resolve_followup_query", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "resolve_social_and_operational_intent", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "latest_user_message", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "build_social_only_reply", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "resolved_ollama_runtime", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "warm_ollama_chat_runtime", _stub_dict)
    monkeypatch.setattr(runtime_dependencies, "build_unverified_pdf_reply", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "build_docx_bytes", _stub_bytes)
    monkeypatch.setattr(runtime_dependencies, "build_export_filename", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "infer_export_title", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "build_attachment_prompt_block", _stub_str)
    monkeypatch.setattr(runtime_dependencies, "parse_attachment_payloads", _stub_tuple)

    deps = runtime_dependencies.build_runtime_lex_dependencies()

    assert deps.requests_module.__class__.__name__ == "_FakeRequests"
    assert deps.build_studio_context is _stub_dict
    assert deps.build_prompt is _stub_str
    assert deps.parse_attachment_payloads is _stub_tuple


def test_require_authenticated_flask_user_blocca_anonimo():
    app = Flask(__name__)
    app.config["TESTING"] = True

    @runtime_dependencies.require_authenticated_flask_user
    def protected():
        return {"ok": True}, 200

    with app.test_request_context("/assistente"):
        payload, status = protected()

    assert status == 401
    assert payload == {"errore": "non autenticato"}


def test_require_authenticated_flask_user_lascia_passare_utente_autenticato():
    app = Flask(__name__)
    app.config["TESTING"] = True

    @runtime_dependencies.require_authenticated_flask_user
    def protected():
        return {"ok": True}, 200

    with app.test_request_context("/assistente"):
        g.utente_corrente = {"username": "admin"}
        payload, status = protected()

    assert status == 200
    assert payload == {"ok": True}
