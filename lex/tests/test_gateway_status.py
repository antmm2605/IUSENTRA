from lex.service import LexService


def test_gateway_status_espone_provider_senza_chiavi(monkeypatch):
    monkeypatch.setenv("LEX_EXTERNAL_ALLOWED", "1")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-secret")

    payload, status = LexService().gateway_status()

    assert status == 200
    assert payload["ok"] is True
    assert payload["external_allowed"] is True
    assert any(provider["name"] == "ollama" and provider["is_local"] for provider in payload["providers"])
    openrouter = next(provider for provider in payload["providers"] if provider["name"] == "openrouter")
    assert openrouter["has_api_key"] is True
    assert "test-secret" not in str(payload)
