import requests

from lex.gateway.config import ProviderConfig
from lex.gateway.messages import ChatMessage, ProviderResponse
from lex.gateway.providers.base import BaseProvider


class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        self.is_local = config.is_local

    def chat(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        **kwargs,
    ) -> ProviderResponse:
        selected_model = model or self.config.default_model

        headers = {
            "Content-Type": "application/json",
        }

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": selected_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        url = self.config.base_url.rstrip("/") + "/chat/completions"

        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}

        return ProviderResponse(
            content=content,
            provider=self.name,
            model=selected_model,
            tokens_input=usage.get("prompt_tokens"),
            tokens_output=usage.get("completion_tokens"),
            raw=data,
        )
