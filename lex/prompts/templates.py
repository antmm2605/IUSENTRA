"""Builder centralizzato dei prompt Lex."""

from __future__ import annotations

from typing import Any

from .system_prompt import build_system_prompt
from .task_prompts import prompt_for_mode


def build_prompt(*, mode: str = "general", **kwargs: Any) -> str:
    base = build_system_prompt(**kwargs)
    task_block = prompt_for_mode(mode)
    if not task_block:
        return base
    return f"{base}\n\n=== MODALITA' OPERATIVA ===\n{task_block}"
