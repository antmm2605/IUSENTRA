from lex.gateway.config import ProviderConfig
from lex.gateway.providers.base import BaseProvider
from lex.gateway.providers.ollama import OllamaProvider
from lex.gateway.providers.openai_compatible import OpenAICompatibleProvider


def build_provider(config: ProviderConfig) -> BaseProvider:
    if config.kind == "ollama":
        return OllamaProvider(config)

    if config.kind == "openai_compatible":
        return OpenAICompatibleProvider(config)

    raise ValueError(f"Provider non supportato: {config.kind}")
