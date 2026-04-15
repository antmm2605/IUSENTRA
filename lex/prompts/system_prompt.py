"""Facciata del prompt di sistema di Lex."""

from __future__ import annotations

from typing import Any

from web.services.assistente_prompt import build_assistente_prompt


def build_system_prompt(**kwargs: Any) -> str:
    return build_assistente_prompt(**kwargs)
