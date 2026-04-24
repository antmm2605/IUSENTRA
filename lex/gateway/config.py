import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "s", "on"}


@dataclass
class ProviderConfig:
    name: str
    kind: str
    base_url: str
    api_key: str | None = None
    default_model: str = ""
    is_local: bool = False
    enabled: bool = True
    timeout_seconds: int = 120


@dataclass
class GatewayConfig:
    mode: str = "local_first"
    external_allowed: bool = False
    default_provider: str = "ollama"
    default_model: str = "llama3.1:8b"
    providers: dict[str, ProviderConfig] = field(default_factory=dict)

    @staticmethod
    def from_env() -> "GatewayConfig":
        cfg = GatewayConfig(
            mode=os.getenv("LEX_AI_MODE", "local_first").strip(),
            external_allowed=_env_bool("LEX_EXTERNAL_ALLOWED", False),
            default_provider=os.getenv("LEX_DEFAULT_PROVIDER", "ollama").strip(),
            default_model=os.getenv("LEX_DEFAULT_MODEL", "llama3.1:8b").strip(),
        )

        cfg.providers["ollama"] = ProviderConfig(
            name="ollama",
            kind="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip(),
            default_model=os.getenv("OLLAMA_DEFAULT_MODEL", cfg.default_model).strip(),
            is_local=True,
            enabled=_env_bool("OLLAMA_ENABLED", True),
            timeout_seconds=int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120")),
        )

        cfg.providers["lmstudio"] = ProviderConfig(
            name="lmstudio",
            kind="openai_compatible",
            base_url=os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").strip(),
            api_key=os.getenv("LMSTUDIO_API_KEY", "lm-studio"),
            default_model=os.getenv("LMSTUDIO_DEFAULT_MODEL", "local-model").strip(),
            is_local=True,
            enabled=_env_bool("LMSTUDIO_ENABLED", False),
            timeout_seconds=int(os.getenv("LMSTUDIO_TIMEOUT_SECONDS", "120")),
        )

        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        cfg.providers["openrouter"] = ProviderConfig(
            name="openrouter",
            kind="openai_compatible",
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip(),
            api_key=openrouter_key,
            default_model=os.getenv("OPENROUTER_DEFAULT_MODEL", "openrouter/auto").strip(),
            is_local=False,
            enabled=bool(openrouter_key),
            timeout_seconds=int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120")),
        )

        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        cfg.providers["deepseek"] = ProviderConfig(
            name="deepseek",
            kind="openai_compatible",
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").strip(),
            api_key=deepseek_key,
            default_model=os.getenv("DEEPSEEK_DEFAULT_MODEL", "deepseek-chat").strip(),
            is_local=False,
            enabled=bool(deepseek_key),
            timeout_seconds=int(os.getenv("DEEPSEEK_TIMEOUT_SECONDS", "120")),
        )

        return cfg
