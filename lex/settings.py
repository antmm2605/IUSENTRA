"""Impostazioni centrali del modulo Lex."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class LexSettings:
    enabled: bool = True
    default_provider: str = os.getenv("LEX_PROVIDER_DEFAULT", "ollama")
    ollama_model: str = os.getenv("LEX_OLLAMA_MODEL", "llama3")
    max_context_chars: int = int(os.getenv("LEX_MAX_CONTEXT_CHARS", "12000"))
    max_evidence_items: int = int(os.getenv("LEX_MAX_EVIDENCE_ITEMS", "12"))
    enable_memory: bool = os.getenv("LEX_ENABLE_MEMORY", "1") == "1"
    enable_telemetry: bool = os.getenv("LEX_ENABLE_TELEMETRY", "1") == "1"
    strict_citations: bool = os.getenv("LEX_STRICT_CITATIONS", "1") == "1"


# ---------------------------------------------------------------------------
# Parametri di generazione del modello locale (unico punto di verità).
#
# Usati sia dal percorso governato (`OllamaProvider`) sia dal percorso in
# streaming (`LocalLLMProvider`): stesso `num_ctx` in entrambi, così Ollama non
# ricarica il modello passando da un percorso all'altro. I valori si leggono a
# ogni chiamata dalle variabili d'ambiente: un cambio di configurazione non
# richiede di toccare il codice.
# ---------------------------------------------------------------------------

_VERO = {"1", "true", "vero", "yes", "si", "sì", "on"}
_FALSO = {"0", "false", "falso", "no", "off"}


def _env_int(name: str, default: int, *, minimo: int = 1) -> int:
    try:
        value = int(str(os.getenv(name, "") or "").strip())
    except ValueError:
        return default
    return value if value >= minimo else default


def _env_float(name: str, default: float, *, minimo: float = 0.0, massimo: float = 2.0) -> float:
    try:
        value = float(str(os.getenv(name, "") or "").strip().replace(",", "."))
    except ValueError:
        return default
    return value if minimo <= value <= massimo else default


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "") or "").strip().lower()
    if raw in _VERO:
        return True
    if raw in _FALSO:
        return False
    return default


@dataclass(frozen=True, slots=True)
class LexGenerationSettings:
    """Parametri di generazione e budget del contesto per il modello locale."""

    num_ctx: int = 8192
    num_predict: int = 700
    temperature: float = 0.2
    timeout_s: int = 300
    think: bool = False
    # Stessa lista che seleziona il retrieval (12) e che controlla la guardia
    # anti-allucinazione: il modello non vede mai piu' fonti di quelle controllate.
    max_evidence_items: int = 12
    evidence_max_chars: int = 1600
    studio_context_max_chars: int = 6000
    # Margine per il template di chat del modello (ruoli, token speciali).
    template_overhead_tokens: int = 64

    @property
    def input_budget_tokens(self) -> int:
        """Token disponibili per system prompt + messaggio utente."""
        return max(self.num_ctx - self.num_predict - self.template_overhead_tokens, 256)

    def ollama_options(self) -> dict[str, float | int]:
        return {
            "temperature": self.temperature,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict,
        }

    @classmethod
    def from_env(cls) -> LexGenerationSettings:
        default = cls()
        return cls(
            num_ctx=_env_int("LEX_NUM_CTX", default.num_ctx, minimo=1024),
            num_predict=_env_int("LEX_NUM_PREDICT", default.num_predict, minimo=64),
            temperature=_env_float("LEX_TEMPERATURE", default.temperature),
            timeout_s=_env_int("LEX_LLM_TIMEOUT_S", default.timeout_s, minimo=5),
            think=_env_bool("LEX_THINK", default.think),
            max_evidence_items=_env_int("LEX_MAX_EVIDENCE_ITEMS", default.max_evidence_items),
            evidence_max_chars=_env_int("LEX_EVIDENCE_MAX_CHARS", default.evidence_max_chars, minimo=200),
            studio_context_max_chars=_env_int(
                "LEX_STUDIO_CONTEXT_MAX_CHARS", default.studio_context_max_chars, minimo=0
            ),
        )


def lex_generation_settings() -> LexGenerationSettings:
    """Parametri correnti, letti dalle variabili d'ambiente a ogni chiamata."""
    return LexGenerationSettings.from_env()
