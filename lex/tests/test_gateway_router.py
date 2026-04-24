from lex.gateway.config import GatewayConfig, ProviderConfig
from lex.gateway.privacy_guard import PrivacyGuard
from lex.gateway.router import LexRouter


def make_config(external_allowed=False):
    return GatewayConfig(
        mode="local_first",
        external_allowed=external_allowed,
        providers={
            "ollama": ProviderConfig(
                name="ollama",
                kind="ollama",
                base_url="http://127.0.0.1:11434",
                default_model="llama3.1:8b",
                is_local=True,
                enabled=True,
            ),
            "openrouter": ProviderConfig(
                name="openrouter",
                kind="openai_compatible",
                base_url="https://openrouter.ai/api/v1",
                api_key="test",
                default_model="openrouter/auto",
                is_local=False,
                enabled=True,
            ),
        },
    )


def test_sensitive_goes_local_only():
    guard = PrivacyGuard()
    privacy = guard.classify_text("Fascicolo RG 1234/2024 cliente RSSMRA80A01H501U")
    router = LexRouter(make_config(external_allowed=True))
    decision = router.route("general", privacy, allow_external=True)
    assert decision.provider_order == ["ollama"]
    assert decision.external_allowed is False


def test_public_can_use_external_after_local_when_allowed():
    guard = PrivacyGuard()
    privacy = guard.classify_text("Scrivi una checklist generale sul deposito telematico senza dati reali.")
    router = LexRouter(make_config(external_allowed=True))
    decision = router.route("general", privacy, allow_external=True)
    assert decision.provider_order == ["ollama", "openrouter"]
    assert decision.external_allowed is True
