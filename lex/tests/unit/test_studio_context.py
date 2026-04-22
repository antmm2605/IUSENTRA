from __future__ import annotations

from types import SimpleNamespace

from lex.context.studio_context import build_studio_context


def test_build_studio_context_unisce_seed_http_al_payload_live(monkeypatch):
    monkeypatch.setattr(
        "lex.context.studio_context._build_lex_studio_context",
        lambda *args, **kwargs: {"sources": [], "focus_label": "generico", "source_mode": "balanced"},
    )
    request = SimpleNamespace(
        tenant_id="antonella-mammola",
        workflow_hint="economico",
        query="vorrei fare un preventivo",
        metadata={
            "studio_context_seed": {
                "sources": [{"id": "prev-1", "title": "Preventivo guidato"}],
                "focus_label": "preventivi",
                "focus_topic": "preventivi",
                "request_profile": {"intent": "preventivo_guidato"},
            }
        },
    )

    payload = build_studio_context(request)

    assert payload["focus_label"] == "preventivi"
    assert payload["focus_topic"] == "preventivi"
    assert payload["sources"][0]["title"] == "Preventivo guidato"
    assert payload["request_profile"]["intent"] == "preventivo_guidato"


def test_build_studio_context_usa_seed_anche_se_il_builder_live_fallisce(monkeypatch):
    monkeypatch.setattr(
        "lex.context.studio_context._build_lex_studio_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    request = SimpleNamespace(
        tenant_id="antonella-mammola",
        workflow_hint="economico",
        query="vorrei fare un preventivo",
        metadata={
            "studio_context_seed": {
                "sources": [{"id": "prev-1", "title": "Preventivo guidato"}],
                "focus_label": "preventivi",
                "focus_topic": "preventivi",
            }
        },
    )

    payload = build_studio_context(request)

    assert payload["tenant_id"] == "antonella-mammola"
    assert payload["workflow_hint"] == "economico"
    assert payload["sources"][0]["title"] == "Preventivo guidato"
