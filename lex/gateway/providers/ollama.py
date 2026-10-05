import requests

from lex.gateway.config import ProviderConfig
from lex.gateway.messages import ChatMessage, ProviderResponse
from lex.gateway.providers.base import BaseProvider


def _num_ctx() -> int:
    from lex.settings import lex_generation_settings

    return lex_generation_settings().num_ctx


def _rifiuta_think(response) -> bool:
    try:
        return "think" in str(response.text or "").lower()
    except Exception:
        return False


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
            # Stesso contesto di Lex (LEX_NUM_CTX, 8192): senza num_ctx Ollama tronca in silenzio
            # il prompt lungo dell'editor atti al contesto predefinito del modello.
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": _num_ctx(),
            },
            # Nessun ragionamento prima della risposta (come il percorso Lex governato).
            "think": False,
        }

        url = self.config.base_url.rstrip("/") + "/api/chat"

        response = requests.post(
            url,
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        if getattr(response, "status_code", 200) == 400 and _rifiuta_think(response):
            # Modelli senza supporto al ragionamento: si ripete una volta senza il campo.
            payload.pop("think", None)
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
