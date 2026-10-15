"""Il comando pubblico non avvia ricerche o contesti interni estranei."""

import json
from types import SimpleNamespace

from flask import Flask

from lex.orchestrator_http import build_context_response, chat_response


def test_public_stream_preserves_payload_and_skips_internal_context(monkeypatch):
    app = Flask(__name__)
    authorized = []

    def forbidden(*args, **kwargs):
        raise AssertionError("Lavorazione interna estranea alla richiesta pubblica")

    monkeypatch.setattr("lex.orchestrator_http._risposta_certa_http", forbidden)
    monkeypatch.setattr("lex.orchestrator_http.build_context_payload", forbidden)
    payload = {"answer": "Confronto con fonte letta", "sources": [{"url": "https://example.org"}]}

    def steps(**kwargs):
        assert "fascicolo_id" not in kwargs["metadata"]
        yield {"progress": "Lettura delle fonti"}
        yield {"payload": payload}

    monkeypatch.setattr("lex.http_bounded_bridge._free_web_payload_steps", steps)
    routing = SimpleNamespace(is_social_only=False, effective_query="Leggi la pagina pubblica",
                              is_social_with_request=False)
    dependencies = SimpleNamespace(
        resolve_social_and_operational_intent=lambda *args, **kwargs: routing,
        resolve_followup_query=lambda query, **kwargs: SimpleNamespace(effective_query=query),
        resolved_runtime=forbidden,
    )
    orchestrator = SimpleNamespace(dependencies=dependencies,
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kwargs: authorized.append(kwargs)))
    with app.test_request_context():
        response = chat_response(orchestrator, user="user-a", studio="studio-a",
            data={"free_web_enabled": True, "fascicolo_id": "private-case"},
            resolve_messages=lambda **kwargs: ("Leggi la pagina pubblica", "", []),
            messages_with_effective_question=forbidden)
        body = response.get_data(as_text=True)
    assert len(authorized) == 1
    events = [json.loads(line[6:]) for line in body.splitlines()
              if line.startswith("data: ") and line != "data: [DONE]"]
    assert events == [{"progress": "Lettura delle fonti"}, {"payload": payload}]
    assert "X-Accel-Buffering" in response.headers


def test_public_json_skips_private_builder_and_runtime(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Il contesto privato non è necessario")

    monkeypatch.setattr("lex.orchestrator_http.build_context_payload", forbidden)
    routing = SimpleNamespace(is_social_only=False, effective_query="Leggi la pagina",
                              is_social_with_request=False)
    calls = []

    def public_payload(**kwargs):
        calls.append(kwargs)
        return {"answer": "Testo letto", "sources": []}

    monkeypatch.setattr("lex.http_bounded_bridge._free_web_direct_payload", public_payload)
    orchestrator = SimpleNamespace(
        auth_guard=SimpleNamespace(ensure_can_access=lambda **kwargs: None),
        dependencies=SimpleNamespace(
            resolve_social_and_operational_intent=lambda *args, **kwargs: routing,
            resolve_followup_query=lambda query, **kwargs: SimpleNamespace(effective_query=query),
            resolved_runtime=forbidden))
    payload, status = build_context_response(orchestrator, user="a", studio="b",
        data={"free_web_enabled": True, "fascicolo_id": "private-case"},
        resolve_messages=lambda **kwargs: ("Leggi la pagina", "", []))
    assert status == 200 and payload["answer"] == "Testo letto"
    assert len(calls) == 1 and "fascicolo_id" not in calls[0]["metadata"]
