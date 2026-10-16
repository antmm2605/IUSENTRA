"""Il comando pubblico non avvia ricerche o contesti interni estranei."""

import json
from types import SimpleNamespace

import pytest
from flask import Flask

from lex.orchestrator_http import build_context_response, chat_response


def test_governed_stream_delivers_sources_warnings_and_export_policy(monkeypatch):
    question = "Analizza la norma acquisita."
    payload = {"answer": "Testo motivato.", "warnings": ["Edizione acquisita."],
               "sources": [{"title": "Articolo", "url": "https://example.org/norma"}], "disable_exports": True}
    monkeypatch.setattr("lex.orchestrator_http._risposta_certa_http", lambda *args: "")
    monkeypatch.setattr("lex.orchestrator_http.build_context_payload", lambda *args, **kwargs: {"effective_question": question})
    monkeypatch.setattr("lex.orchestrator_http.build_bounded_http_payload", lambda **kwargs: payload)
    routing = SimpleNamespace(is_social_only=False, effective_query=question, is_social_with_request=False)
    orchestrator = SimpleNamespace(auth_guard=SimpleNamespace(ensure_can_access=lambda **kwargs: None),
        dependencies=SimpleNamespace(resolve_social_and_operational_intent=lambda *args, **kwargs: routing,
            resolve_followup_query=lambda *args, **kwargs: SimpleNamespace(effective_query=question),
            resolved_runtime=lambda: {}, build_unverified_pdf_reply=lambda *args: ""))
    with Flask(__name__).test_request_context():
        response = chat_response(orchestrator, user="a", studio="b", data={},
            resolve_messages=lambda **kwargs: (question, "", []), messages_with_effective_question=lambda *args: [])
        events = [json.loads(line[6:]) for line in response.get_data(as_text=True).splitlines()
                  if line.startswith("data: ") and line != "data: [DONE]"]
    assert events == [{"payload": payload}]


@pytest.mark.parametrize("manual", [True, False])
def test_public_stream_preserves_payload_and_skips_internal_context(monkeypatch, manual):
    app = Flask(__name__)
    authorized = []

    def forbidden(*args, **kwargs):
        raise AssertionError("Lavorazione interna estranea alla richiesta pubblica")

    monkeypatch.setattr("lex.orchestrator_http._risposta_certa_http", forbidden)
    monkeypatch.setattr("lex.orchestrator_http.build_context_payload", forbidden)
    payload = {"answer": "Confronto con fonte letta", "sources": [{"url": "https://example.org"}]}

    question = "Leggi la pagina pubblica https://example.org . Non usare dati dello studio."

    def steps(**kwargs):
        assert "fascicolo_id" not in kwargs["metadata"]
        assert kwargs["resolved_effective_question"] == question
        assert kwargs["metadata"]["manual_free_web_enabled"] is manual
        assert kwargs["metadata"]["public_web_activation"] == ("manual_toggle" if manual else "explicit_url_request")
        yield {"progress": "Lettura delle fonti"}
        yield {"payload": payload}

    monkeypatch.setattr("lex.http_bounded_bridge._free_web_payload_steps", steps)
    routing = SimpleNamespace(is_social_only=False, effective_query=question,
                              is_social_with_request=False)
    dependencies = SimpleNamespace(
        resolve_social_and_operational_intent=lambda *args, **kwargs: routing,
        resolve_followup_query=lambda query, **kwargs: SimpleNamespace(
                effective_query=query if manual else "Dati riservati della cronologia"),
        resolved_runtime=forbidden,
    )
    orchestrator = SimpleNamespace(dependencies=dependencies,
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kwargs: authorized.append(kwargs)))
    with app.test_request_context():
        response = chat_response(orchestrator, user="user-a", studio="studio-a",
            data={"free_web_enabled": manual, "fascicolo_id": "private-case"},
            resolve_messages=lambda **kwargs: (question, "Dati privati del cliente", []),
            messages_with_effective_question=forbidden)
        body = response.get_data(as_text=True)
    assert len(authorized) == 1
    events = [json.loads(line[6:]) for line in body.splitlines()
              if line.startswith("data: ") and line != "data: [DONE]"]
    assert events == [{"progress": "Lettura delle fonti"}, {"payload": payload}]
    assert "X-Accel-Buffering" in response.headers


@pytest.mark.parametrize("manual", [True, False])
def test_public_json_skips_private_builder_and_runtime(monkeypatch, manual):
    def forbidden(*args, **kwargs):
        raise AssertionError("Il contesto privato non è necessario")

    monkeypatch.setattr("lex.orchestrator_http.build_context_payload", forbidden)
    question = "Leggi la pagina pubblica https://example.org . Non usare dati dello studio."
    routing = SimpleNamespace(is_social_only=False, effective_query=question,
                              is_social_with_request=False)
    calls = []

    def public_payload(**kwargs):
        assert kwargs["resolved_effective_question"] == question
        assert kwargs["metadata"]["manual_free_web_enabled"] is manual
        assert kwargs["metadata"]["public_web_activation"] == ("manual_toggle" if manual else "explicit_url_request")
        calls.append(kwargs)
        return {"answer": "Testo letto", "sources": []}

    monkeypatch.setattr("lex.http_bounded_bridge._free_web_direct_payload", public_payload)
    orchestrator = SimpleNamespace(
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kwargs: None),
        dependencies=SimpleNamespace(
            resolve_social_and_operational_intent=lambda *args, **kwargs: routing,
            resolve_followup_query=lambda query, **kwargs: SimpleNamespace(
                effective_query=query if manual else "Dati riservati della cronologia"),
            resolved_runtime=forbidden))
    payload, status = build_context_response(orchestrator, user="a", studio="b",
        data={"free_web_enabled": manual, "fascicolo_id": "private-case"},
        resolve_messages=lambda **kwargs: (question, "Dati privati del cliente", []))
    assert status == 200 and payload["answer"] == "Testo letto"
    assert len(calls) == 1 and "fascicolo_id" not in calls[0]["metadata"]


@pytest.mark.parametrize("stream", [True, False])
def test_explicit_public_pages_do_not_discard_uploaded_documents(monkeypatch, stream):
    app = Flask(__name__)
    question = "Leggi questa pagina pubblica https://example.org"

    def attachment_route(*args, **kwargs):
        raise RuntimeError("Percorso degli allegati preservato")

    monkeypatch.setattr("lex.orchestrator_http._risposta_certa_http", attachment_route)
    routing = SimpleNamespace(is_social_only=False, effective_query=question, is_social_with_request=False)
    orchestrator = SimpleNamespace(
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kwargs: None),
        dependencies=SimpleNamespace(
            resolve_social_and_operational_intent=lambda *args, **kwargs: routing,
            resolve_followup_query=lambda query, **kwargs: SimpleNamespace(effective_query=query),
            resolved_runtime=attachment_route))
    data = {"free_web_enabled": False, "attachments": [{"id": "documento-caricato"}]}
    kwargs = dict(user="a", studio="b", data=data,
                  resolve_messages=lambda **kwargs: (question, "", []))
    with app.test_request_context(), pytest.raises(RuntimeError, match="allegati preservato"):
        if stream:
            chat_response(orchestrator, **kwargs, messages_with_effective_question=lambda *args: [])
        else:
            build_context_response(orchestrator, **kwargs)
    assert "source_mode" not in data and data["free_web_enabled"] is False
