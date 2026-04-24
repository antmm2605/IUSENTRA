from abc import ABC, abstractmethod
from typing import Any

from lex.gateway.messages import ChatMessage, ProviderResponse


class BaseProvider(ABC):
    name: str
    is_local: bool

    @abstractmethod
    def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs: Any,
    ) -> ProviderResponse:
        raise NotImplementedError
