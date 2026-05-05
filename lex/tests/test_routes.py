from __future__ import annotations

from flask import Flask, g

from lex.blueprint import create_lex_blueprint
from lex.dependencies import LexDependencies


class FakeRequests:
    class exceptions:
        class ConnectionError(Exception):
            pass

    @staticmethod
    def get(*args, **kwargs):
        class Resp:
            @staticmethod
            def json():
                return {"models": [{"name": "mistral"}]}

        return Resp()


class FakeRouting:
    is_social_only = False
    is_social_with_request = False
    social_kind = ""
    social_prefix = ""
    effective_query = ""
    raw_text = ""
    is_daily_overview = False
    is_followup = False
    reused_previous_topic = False


class FakeFollowup:
    effective_query = ""
    reused_previous_topic = False
    previous_user_text = ""
    is_web_request = False
    needs_web_search = False


class FakeLanguageGuidance:
    opening_line = ""
    prompt_block = ""
    mode = "general"


def dependency_factory() -> LexDependencies:
    return LexDependencies(
        requests_module=FakeRequests(),
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
        },
        warm_studio_context=lambda **kwargs: {"sources": []},
        build_today_summary=lambda **kwargs: {},
        build_language_guidance=lambda **kwargs: FakeLanguageGuidance(),
        build_prompt=lambda **kwargs: "PROMPT",
        resolve_followup_query=lambda *args, **kwargs: FakeFollowup(),
        resolve_social_and_operational_intent=lambda *args, **kwargs: FakeRouting(),
        latest_user_message=lambda *args, **kwargs: "",
        build_social_only_reply=lambda *args, **kwargs: "Dimmi pure.",
        resolved_runtime=lambda: {
            "api_base_url": "http://localhost:11434/api",
            "base_url": "http://localhost:11434",
            "chat_model": "mistral",
        },
        warm_runtime=lambda: {"ok": True},
        build_unverified_pdf_reply=lambda *args, **kwargs: "",
        build_docx_bytes=lambda **kwargs: b"docx-content",
        build_export_filename=lambda title, ext: f"{title}.{ext}",
        infer_export_title=lambda **kwargs: "Export Lex",
        build_attachment_prompt_block=lambda attachments: "ALLEGATI",
        parse_attachment_payloads=lambda files: (files, []),
    )


def make_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret"

    @app.before_request
    def _login_test_user():
        g.utente_corrente = {"username": "test"}

    app.register_blueprint(
        create_lex_blueprint(
            dependency_factory=dependency_factory,
            login_required=None,
        )
    )
    return app


def test_lex_blueprint_registers_expected_routes():
    app = make_app()
    rules = {rule.rule for rule in app.url_map.iter_rules()}

    assert "/lex" in rules
    assert "/api/assistente/stato" in rules
    assert "/api/assistente/context" in rules
    assert "/api/assistente/warmup" in rules
    assert "/api/assistente/attachments" in rules
    assert "/api/assistente/documento" in rules
    assert "/api/assistente/chat" in rules


def test_assistente_stato_endpoint_returns_200():
    app = make_app()
    client = app.test_client()

    response = client.get("/api/assistente/stato")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["modello_attivo"] == "mistral"


def test_assistente_attachments_endpoint_returns_attachment_evidence_metadata():
    app = make_app()
    client = app.test_client()

    response = client.post(
        "/api/assistente/attachments",
        json={"files": [{"name": "atto.pdf"}]},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["attachments"] == [{"name": "atto.pdf"}]
    assert payload["prompt_block"] == ""
    assert payload["evidence_mode"] == "attachment_evidence"


def test_lex_fascicolo_standalone_page_removed():
    app = make_app()
    client = app.test_client()

    response = client.get("/lex?context=fascicolo&id_fasc=17A38FB6")

    assert response.status_code == 410
    assert "pagina Lex standalone dei fascicoli" in response.get_data(as_text=True)
    assert "Ciao, sono Lex" not in response.get_data(as_text=True)
