from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass
class ChatMessage:
    role: Role
    content: str


@dataclass
class ProviderResponse:
    content: str
    provider: str
    model: str
    tokens_input: int | None = None
    tokens_output: int | None = None
    raw: dict | None = None
