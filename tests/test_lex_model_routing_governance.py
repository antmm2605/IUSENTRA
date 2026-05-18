from __future__ import annotations

from types import SimpleNamespace

from lex.providers.registry import LEX_MODEL_ROUTING_SCHEMA, ProviderRegistry


def _request(**metadata):
    return SimpleNamespace(metadata=metadata)


def test_model_routing_espone_policy_deterministica_senza_llm():
    registry = ProviderRegistry()

    metadata = registry.get_routing_metadata(_request(), {}, "cabina", {})

    assert metadata["schema"] == LEX_MODEL_ROUTING_SCHEMA
    assert metadata["provider"] == "deterministic"
    assert metadata["profile"] == "deterministic"
    assert metadata["llm_used"] is False
    assert metadata["profile_policy"]["cost_tier"] == "none"


def test_model_routing_giurisprudenza_specifica_usa_reasoner_legale():
    registry = ProviderRegistry()

    metadata = registry.get_routing_metadata(_request(), {}, "giurisprudenza_specifica", {"items": [object()]})

    assert metadata["provider"] == "ollama"
    assert metadata["profile"] == "legal_reasoner"
    assert metadata["llm_used"] is True
    assert "dato certo" in metadata["profile_policy"]["quality_gate"]


def test_model_routing_provider_esterno_richiede_abilitazione(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.delenv("LEX_EXTERNAL_ALLOWED", raising=False)

    denied = registry.get_routing_metadata(_request(force_provider="openai"), {}, "normativa", {})

    assert denied["provider"] == "ollama"
    assert denied["external_allowed"] is False
    assert "non autorizzato" in denied["reason"]

    monkeypatch.setenv("LEX_EXTERNAL_ALLOWED", "1")
    allowed = registry.get_routing_metadata(_request(force_provider="openai"), {}, "normativa", {})

    assert allowed["provider"] == "openai"
    assert allowed["external_allowed"] is True


def test_model_routing_non_espone_credenziali_ollama(monkeypatch):
    registry = ProviderRegistry()
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://utente:segreto@ollama.lan:11434/api")

    metadata = registry.get_routing_metadata(_request(), {}, "normativa", {})

    assert metadata["ollama_url"] == "http://ollama.lan:11434"
    assert "segreto" not in metadata["ollama_url"]
    assert "utente" not in metadata["ollama_url"]
