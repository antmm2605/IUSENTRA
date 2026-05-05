from __future__ import annotations

from types import SimpleNamespace

from lex.providers.ollama_provider import OllamaProvider


def _assert_skipped(monkeypatch, workflow: str):
    called = {"value": False}

    def fail_call(*args, **kwargs):
        called["value"] = True
        raise AssertionError("Ollama non deve essere chiamato senza evidenze strict")

    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {
            "api_base_url": "http://127.0.0.1:11434/api",
            "chat_model": "mistral",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr("lex.providers.ollama_provider._call_ollama", fail_call)

    draft = OllamaProvider().generate(
        request=SimpleNamespace(query="test"),
        context={},
        evidence={"items": [], "citations": [], "official_sources": []},
        workflow=workflow,
    )

    assert called["value"] is False
    assert draft.metadata["provider"] == "ollama"
    assert draft.metadata["model"] == "mistral"
    assert draft.metadata["workflow"] == workflow
    assert draft.metadata["evidence_count"] == 0
    assert draft.metadata["status"] == "skipped"
    assert draft.metadata["skipped_generation_reason"] == "strict_workflow_without_evidence"
    assert "base verificata sufficiente" in draft.text or "fonti ufficiali" in draft.text


def test_normativa_senza_evidenze_non_chiama_ollama(monkeypatch):
    _assert_skipped(monkeypatch, "normativa")


def test_giurisprudenza_senza_evidenze_non_chiama_ollama(monkeypatch):
    _assert_skipped(monkeypatch, "giurisprudenza")
