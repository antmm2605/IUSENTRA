"""Provider locale Ollama per Lex."""

from __future__ import annotations

import json
from typing import Any, Callable


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
        return {
            "model": chat_model,
            "messages": [{"role": "system", "content": system_content}] + list(llm_messages or []),
            "stream": True,
            "keep_alive": keep_alive,
            "options": {"temperature": 0.3, "num_ctx": 4096},
        }

    def stream_chat(
        self,
        *,
        requests_module,
        api_base_url: str,
        payload: dict[str, Any],
        base_url: str,
        opening_line: str = "",
    ) -> Callable[[], Any]:
        def generate():
            try:
                if opening_line:
                    yield f"data: {json.dumps({'token': opening_line + ' '})}\n\n"
                response = requests_module.post(
                    f"{api_base_url}/chat",
                    json=payload,
                    stream=True,
                    timeout=180,
                )
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
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
            except Exception as exc:
                yield f"data: {json.dumps({'errore': str(exc)})}\n\n"
                yield "data: [DONE]\n\n"

        return generate
