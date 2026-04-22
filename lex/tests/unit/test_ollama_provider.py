from types import SimpleNamespace

from lex.providers.ollama_provider import OllamaProvider


def test_ollama_provider_non_si_rompe_con_payload_senza_evidenze(monkeypatch):
    provider = OllamaProvider()

    monkeypatch.setattr(
        "lex.providers.ollama_provider._resolve_runtime",
        lambda: {
            "api_base_url": "http://127.0.0.1:11434/api",
            "chat_model": "mistral",
            "keep_alive": "10m",
        },
    )
    monkeypatch.setattr(
        "lex.providers.ollama_provider._call_ollama",
        lambda payload, api_base_url, timeout=120: "Risposta con fallback web gestito correttamente.",
    )

    draft = provider.generate(
        request=SimpleNamespace(query="sentenza n. 8785 del 08/04/2026"),
        context={"focus": "ricerca_legale"},
        evidence={"items": [], "citations": [], "official_sources": []},
        workflow="giurisprudenza",
    )

    assert "fallback web" in draft.text.lower()
    assert draft.metadata["status"] == "ok"
    assert draft.metadata["evidence_count"] == 0
