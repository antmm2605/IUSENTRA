"""Response DTO lato API per Lex."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AskLexAPIResponse:
    ok: bool
    answer: str = ""
    warnings: list[str] = field(default_factory=list)
