"""Provider locale Ollama per Lex (percorso in streaming).

Parametri di generazione da `lex.settings.lex_generation_settings()`, gli stessi
del percorso governato (`OllamaProvider`): stesso `num_ctx`, quindi nessun
ricaricamento del modello passando da un percorso all'altro.
"""

from __future__ import annotations

import json
from time import monotonic
from typing import Any, Callable

from lex.settings import lex_generation_settings

from .prompt_budget import ThinkStreamFilter


class LocalLLMProvider:
    def build_chat_payload(
        self,
        *,
        runtime: dict[str, Any],
        llm_messages: list[dict[str, object]],
        system_content: str,
    ) -> dict[str, Any]:
        chat_model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
        keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"
        settings = lex_generation_settings()
        return {
            "model": chat_model,
            "messages": [{"role": "system", "content": system_content}] + list(llm_messages or []),
            "stream": True,
            "keep_alive": keep_alive,
            "think": settings.think,
            "options": settings.ollama_options(),
        }

    def stream_chat(
        self,
        *,
        requests_module,
        api_base_url: str,
        payload: dict[str, Any],
        base_url: str,
        opening_line: str = "",
        on_first_token: Callable[[float], None] | None = None,
        started_at: float | None = None,
    ) -> Callable[[], Any]:
        timeout_s = lex_generation_settings().timeout_s

        def _post(body: dict[str, Any]):
            return requests_module.post(
                f"{api_base_url}/chat",
                json=body,
                stream=True,
                timeout=timeout_s,
            )

        def generate():
            first_token_emitted = False
            think_filter = ThinkStreamFilter()
            try:
                if opening_line:
                    if not first_token_emitted and on_first_token is not None:
                        on_first_token(((monotonic() - (started_at or monotonic())) * 1000))
                        first_token_emitted = True
                    yield f"data: {json.dumps({'token': opening_line + ' '})}\n\n"
                response = _post(payload)
                if getattr(response, "status_code", 200) == 400 and "think" in payload:
                    # Modello senza supporto al ragionamento: si ripete senza il campo.
                    body_text = str(getattr(response, "text", "") or "")
                    if "think" in body_text.lower():
                        response = _post({key: value for key, value in payload.items() if key != "think"})
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("error"):
                        msg = "Il modello locale non ha risposto correttamente. Riprova tra poco."
                        yield f"data: {json.dumps({'errore': msg})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    token = think_filter.feed(chunk.get("message", {}).get("content", ""))
                    if chunk.get("done"):
                        token += think_filter.flush()
                    if token:
                        if not first_token_emitted and on_first_token is not None:
                            on_first_token(((monotonic() - (started_at or monotonic())) * 1000))
                            first_token_emitted = True
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
                rest = think_filter.flush()
                if rest:
                    yield f"data: {json.dumps({'token': rest})}\n\n"
                yield "data: [DONE]\n\n"
                return
            except requests_module.exceptions.ConnectionError:
                msg = (
                    "Ollama non e' raggiungibile. "
                    "Assicurati che Ollama sia avviato con: `ollama serve`\n"
                    f"URL configurato: {base_url}"
                )
                yield f"data: {json.dumps({'errore': msg})}\n\n"
                yield "data: [DONE]\n\n"
            except getattr(requests_module.exceptions, "Timeout", ()):
                msg = f"Il modello locale non ha risposto entro {timeout_s} secondi. Riprova tra poco."
                yield f"data: {json.dumps({'errore': msg})}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as exc:
                yield f"data: {json.dumps({'errore': str(exc)})}\n\n"
                yield "data: [DONE]\n\n"

        return generate
