import requests

from lex.gateway.config import ProviderConfig
from lex.gateway.messages import ChatMessage, ProviderResponse
from lex.gateway.providers.base import BaseProvider


class OpenAICompatibleProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name
        self.is_local = config.is_local

    def misura_prompt(self, sistema: str, messaggio: str) -> dict:
        """Tokenizer e template del solo llama-server locale realmente caricato.

        Non esegue inferenza. Nessun invio aggiuntivo a provider esterni.
        """
        import hashlib
        import time

        if not self.is_local or self.name != "llamacpp":
            raise ValueError("Misura del prompt riservata al provider llama.cpp locale")
        base = self.config.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        timeout = min(30, self.config.timeout_seconds)
        cached = getattr(self, "_contesto_misurato", None)
        if cached is None or time.monotonic() - cached[0] > 60:
            response = requests.get(base + "/props", headers=headers, timeout=timeout)
            response.raise_for_status()
            props = response.json()
            size = (props.get("default_generation_settings") or {}).get("n_ctx")
            if type(size) is not int or size <= 0:
                raise ValueError("llama-server non ha dichiarato la finestra effettiva del contesto")
            cached = (time.monotonic(), size)
            self._contesto_misurato = cached
        response = requests.post(base + "/apply-template", headers=headers, timeout=timeout, json={
            "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": messaggio}],
            "chat_template_kwargs": {"enable_thinking": False},
        })
        response.raise_for_status()
        prompt = response.json().get("prompt")
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("Template effettivo del modello non disponibile")
        response = requests.post(base + "/tokenize", headers=headers, timeout=timeout,
                                 json={"content": prompt, "add_special": False, "parse_special": True})
        response.raise_for_status()
        tokens = response.json().get("tokens")
        if not isinstance(tokens, list) or any(type(t) is not int for t in tokens):
            raise ValueError("Risposta del tokenizer non valida")
        return {"tokens_input": len(tokens), "contesto": cached[1],
                "sha256_template_applicato": hashlib.sha256(prompt.encode()).hexdigest()}

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
        extra = kwargs.get("extra_body")
        if isinstance(extra, dict):
            payload.update({k: v for k, v in extra.items() if k not in payload})

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
