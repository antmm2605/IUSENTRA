"""Request DTO lato API per Lex."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AskLexAPIRequest:
    tenant_id: str
    user_id: str
    session_id: str
    query: str
