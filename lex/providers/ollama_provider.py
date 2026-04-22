"""Provider applicativo Ollama posseduto da Lex.

Chiama in modo sincrono il runtime Ollama locale tramite l'HTTP client
configurato. Costruisce un prompt completo (sistema + contesto + evidenze +
domanda), esegue la generazione non-streaming e restituisce la bozza pronta
per il passaggio successivo della pipeline Lex.
"""

from __future__ import annotations

import json
from typing import Any

from pct.local_ai import OllamaHttpClient

from .base import BaseProvider
from lex.contracts import ProviderDraft


_FALLBACK_SYSTEM_PROMPT = (
    "Sei Lex, assistente legale professionale per uno studio legale italiano. "
    "Rispondi sempre in italiano formale, in modo accurato, sintetico e citando "
    "le evidenze ricevute quando presenti. Non inventare norme, sentenze o "
    "termini: se non hai informazioni sufficienti, segnala esplicitamente i "
    "dati mancanti e suggerisci la verifica presso le fonti ufficiali."
)


def _safe_import_prompt_builder():
    try:
        from lex.prompts import prompt_builder  # type: ignore

        return prompt_builder
    except Exception:
        return None


def _workflow_specialized_prompt(workflow: str) -> str:
    try:
        from lex.workflows import system_prompt_for

        return system_prompt_for(workflow)
    except Exception:
        return ""


def _build_system_prompt(workflow: str, context: Any) -> str:
    parts: list[str] = []
    prompt_builder = _safe_import_prompt_builder()
    base = ""
    if prompt_builder is not None:
        for fn_name in ("build_system_prompt", "system_prompt_for", "base_system_prompt"):
            fn = getattr(prompt_builder, fn_name, None)
            if callable(fn):
                try:
                    result = fn(workflow=workflow, context=context)  # type: ignore[arg-type]
                    base = str(result or "").strip()
                    if base:
                        break
                except TypeError:
                    try:
                        base = str(fn() or "").strip()
                        if base:
                            break
                    except Exception:
                        continue
                except Exception:
                    continue
        if not base:
            for attr in ("_LEX_VOICE_PROMPT", "_LEX_WRITING_PROMPT", "_LEX_OPERATION_GUARDRAILS"):
                value = getattr(prompt_builder, attr, "")
                if isinstance(value, str) and value.strip():
                    base = value.strip()
                    break
    if not base:
        base = _FALLBACK_SYSTEM_PROMPT
    parts.append(base)

    specialized = _workflow_specialized_prompt(workflow)
    if specialized and specialized not in base:
        parts.append(specialized)
    return "\n\n".join(parts)


def _evidence_items(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return list(evidence.get("items") or [])
    items = getattr(evidence, "items", None)
    if callable(items):
        return []
    return list(items or [])


def _format_evidence(evidence: Any, limit: int = 8) -> str:
    items = _evidence_items(evidence)
    rows: list[str] = []
    for idx, item in enumerate(items[:limit], start=1):
        title = str(
            (item.get("title") if isinstance(item, dict) else getattr(item, "title", "")) or ""
        ).strip() or f"Evidenza {idx}"
        content = str(
            (item.get("content") if isinstance(item, dict) else getattr(item, "content", "")) or ""
        ).strip()
        if not content:
            continue
        rows.append(f"[{idx}] {title}\n{content}")
    return "\n\n".join(rows)


def _format_context(context: Any) -> str:
    if not context:
        return ""
    if isinstance(context, str):
        return context.strip()
    try:
        return json.dumps(context, ensure_ascii=False, default=str, indent=2)
    except Exception:
        return str(context)


def _resolve_runtime() -> dict[str, Any]:
    try:
        from lex.providers.ollama_runtime import resolved_ollama_runtime

        return dict(resolved_ollama_runtime() or {})
    except Exception:
        return {
            "api_base_url": "http://127.0.0.1:11434/api",
            "base_url": "http://127.0.0.1:11434",
            "chat_model": "mistral",
            "keep_alive": "10m",
        }


def _call_ollama(payload: dict[str, Any], api_base_url: str, timeout: int = 120) -> str:
    client = OllamaHttpClient(api_base_url, timeout=timeout)
    response = client.chat(
        str(payload.get("model") or "mistral"),
        messages=list(payload.get("messages") or []),
        keep_alive=str(payload.get("keep_alive") or "10m"),
        options=dict(payload.get("options") or {}),
        timeout=timeout,
    )
    return str(((response.get("message") or {}).get("content") or "")).strip()


class OllamaProvider(BaseProvider):
    provider_name = "ollama"

    def generate(self, request, context, evidence, workflow):
        system_prompt = _build_system_prompt(workflow or "chat", context)
        evidence_text = _format_evidence(evidence)
        context_text = _format_context(context)

        user_sections: list[str] = []
        if context_text:
            user_sections.append(f"Contesto sessione:\n{context_text}")
        if evidence_text:
            user_sections.append(f"Evidenze rilevanti:\n{evidence_text}")
        query = str(getattr(request, "query", "") or "").strip()
        if query:
            user_sections.append(f"Domanda dell'utente:\n{query}")

        user_message = "\n\n".join(user_sections) or query or ""

        runtime = _resolve_runtime()
        model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
        api_base_url = str(runtime.get("api_base_url") or "http://127.0.0.1:11434/api").strip()
        keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"

        payload = {
            "model": model,
            "keep_alive": keep_alive,
            "options": {"temperature": 0.2, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "model": model,
            "workflow": workflow or "chat",
            "evidence_count": len(_evidence_items(evidence)),
        }

        try:
            text = _call_ollama(payload, api_base_url)
            if not text:
                raise RuntimeError("Nessun contenuto generato da Ollama.")
            metadata["status"] = "ok"
            return ProviderDraft(text=text, metadata=metadata)
        except Exception as exc:
            metadata["status"] = "fallback"
            metadata["error"] = str(exc)
            fallback = (
                "Il runtime Ollama non ha risposto correttamente. "
                f"Dettaglio: {exc}. "
                "Riprovare dopo aver verificato che il servizio locale sia attivo."
            )
            return ProviderDraft(text=fallback, metadata=metadata)
