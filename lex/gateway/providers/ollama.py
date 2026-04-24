import requests

from lex.gateway.config import ProviderConfig
from lex.gateway.messages import ChatMessage, ProviderResponse
from lex.gateway.providers.base import BaseProvider


class OllamaProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        self.is_local = True

    def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs,
    ) -> ProviderResponse:
        selected_model = model or self.config.default_model

        payload = {
            "model": selected_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        url = self.config.base_url.rstrip("/") + "/api/chat"

        response = requests.post(
            url,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()

        data = response.json()
        content = data.get("message", {}).get("content", "")

        return ProviderResponse(
            content=content,
            provider=self.name,
            model=selected_model,
            raw=data,
        )
