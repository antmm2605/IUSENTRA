"""Impostazioni centrali del modulo Lex."""

from __future__ import annotations

from dataclasses import dataclass
import os


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
