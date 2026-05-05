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

_LEGAL_AI_RESPONSE_CONTRACT = (
    "Contratto qualita' Lex AI:\n"
    "- Non aprire con saluti o preamboli quando la richiesta e' tecnica o giuridica.\n"
    "- Non usare frasi vaghe come 'iniziamo', 'ci sono diversi aspetti' o 'consulta un avvocato'.\n"
    "- Distingui sempre dato certo, sintesi ricavata dalle fonti, punto da verificare ed effetto pratico.\n"
    "- Se mancano fonti verificabili, scrivi 'non determinabile con le fonti disponibili' e indica cosa acquisire.\n"
    "- Quando usi fonti, rendi riconoscibili titolo, provenienza, data o URL/path se presenti.\n"
    "- Mantieni tono diretto, professionale e operativo per uno studio legale italiano."
)

_META_RESPONSE_MARKERS = (
    "ecco un esempio di risposta",
    "motivazione:",
    "spero che questa risposta",
    "per aiutarti ulteriormente",
    "passi proposti",
    "rischi:",
    "[nome/dipartimento]",
    "simulazione di un sistema di chatbot",
)
_STRICT_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}


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
    if _LEGAL_AI_RESPONSE_CONTRACT not in base:
        parts.append(_LEGAL_AI_RESPONSE_CONTRACT)

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


def _deterministic_runtime_fallback(request, context, evidence, workflow, metadata: dict[str, Any]):
    from .deterministic_provider import DeterministicProvider

    draft = DeterministicProvider().generate(request, context, evidence, workflow or "chat")
    draft.metadata = {
        **dict(getattr(draft, "metadata", {}) or {}),
        **metadata,
        "provider": "ollama",
        "fallback_provider": "deterministic",
        "status": "fallback_runtime_unavailable",
    }
    return draft


def _looks_like_meta_response(text: str) -> bool:
    normalized = " ".join(str(text or "").split()).strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _META_RESPONSE_MARKERS)


def _strict_legal_fallback(workflow: str) -> str:
    if workflow == "giurisprudenza":
        return (
            "Non ho ancora una base verificata sufficiente per chiudere una risposta sulla giurisprudenza richiesta.\n"
            "Indicami numero completo della decisione, ufficio giudiziario o allega il provvedimento, cosi' posso lavorare su riferimenti controllabili."
        )
    if workflow == "normativa":
        return (
            "Non ho ancora una base verificata sufficiente per chiudere una risposta normativa attendibile.\n"
            "Indicami almeno il riferimento dell'atto, l'articolo o la materia, cosi' posso cercare la fonte ufficiale corretta."
        )
    return (
        "La risposta generata non e' abbastanza affidabile per essere proposta come base legale verificata.\n"
        "Serve un riferimento piu' preciso oppure una ricerca sulle fonti ufficiali prima di chiudere il riscontro."
    )


class OllamaProvider(BaseProvider):
    provider_name = "ollama"

    def generate(self, request, context, evidence, workflow):
        system_prompt = _build_system_prompt(workflow or "chat", context)
        evidence_text = _format_evidence(evidence)
        context_text = _format_context(context)
        evidence_items = _evidence_items(evidence)
        runtime = _resolve_runtime()
        model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
        api_base_url = str(runtime.get("api_base_url") or "http://127.0.0.1:11434/api").strip()
        keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"
        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "model": model,
            "workflow": workflow or "chat",
            "evidence_count": len(evidence_items),
        }
        if (workflow or "") in _STRICT_WORKFLOWS and not evidence_items:
            metadata.update(
                {
                    "status": "skipped",
                    "skipped_generation_reason": "strict_workflow_without_evidence",
                }
            )
            return ProviderDraft(text=_strict_legal_fallback(workflow or "chat"), metadata=metadata)

        case_law_rows: list[Any] = []
        case_law_block = ""
        if (workflow or "") == "giurisprudenza":
            try:
                from lex.reasoning.case_law_interpreter import (
                    build_case_law_context,
                    build_case_law_prompt_block,
                )

                case_law_rows = build_case_law_context(evidence_items)
                case_law_block = build_case_law_prompt_block(evidence_items)
            except Exception:
                case_law_rows = []
                case_law_block = ""

        user_sections: list[str] = []
        if context_text:
            user_sections.append(f"Contesto sessione:\n{context_text}")
        if case_law_block:
            user_sections.append(case_law_block)
        if evidence_text:
            user_sections.append(f"Evidenze rilevanti:\n{evidence_text}")
        query = str(getattr(request, "query", "") or "").strip()
        if query:
            user_sections.append(f"Domanda dell'utente:\n{query}")

        user_message = "\n\n".join(user_sections) or query or ""

        payload = {
            "model": model,
            "keep_alive": keep_alive,
            "options": {"temperature": 0.1, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        if isinstance(evidence, dict) and "evidence_sufficient" in evidence:
            metadata["evidence_sufficient"] = bool(evidence.get("evidence_sufficient"))

        try:
            text = _call_ollama(payload, api_base_url)
            if not text:
                raise RuntimeError("Nessun contenuto generato da Ollama.")
            if _looks_like_meta_response(text):
                metadata["status"] = "fallback_meta"
                metadata["meta_response_filtered"] = True
                if (workflow or "") == "giurisprudenza":
                    try:
                        from lex.reasoning.case_law_interpreter import build_deterministic_case_law_answer

                        metadata["case_law_guard_applied"] = True
                        metadata["case_law_fallback_used"] = True
                        metadata["case_law_warnings"] = ["Risposta meta/generica filtrata."]
                        return ProviderDraft(
                            text=build_deterministic_case_law_answer(case_law_rows or evidence_items),
                            metadata=metadata,
                        )
                    except Exception:
                        pass
                if (workflow or "") in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}:
                    return ProviderDraft(
                        text=_strict_legal_fallback(workflow or "chat"),
                        metadata=metadata,
                    )
                from .deterministic_provider import DeterministicProvider

                draft = DeterministicProvider().generate(request, context, evidence, workflow or "chat")
                draft.metadata = {
                    **dict(getattr(draft, "metadata", {}) or {}),
                    "provider": self.provider_name,
                    "fallback_provider": "deterministic",
                    "status": "fallback_meta",
                    "meta_response_filtered": True,
                }
                return draft
            if (workflow or "") == "giurisprudenza":
                try:
                    from lex.guards.case_law_answer_guard import CaseLawAnswerGuard
                    from lex.reasoning.case_law_interpreter import build_deterministic_case_law_answer

                    allowed, warnings = CaseLawAnswerGuard().evaluate(text, evidence_items)
                    if warnings:
                        metadata["case_law_guard_applied"] = True
                        metadata["case_law_warnings"] = warnings
                    if not allowed:
                        text = build_deterministic_case_law_answer(case_law_rows or evidence_items)
                        metadata["case_law_fallback_used"] = True
                    else:
                        metadata["case_law_fallback_used"] = False
                except Exception:
                    pass
            metadata["status"] = "ok"
            return ProviderDraft(text=text, metadata=metadata)
        except Exception as exc:
            metadata["runtime_error_type"] = exc.__class__.__name__
            try:
                from lex.providers.ollama_runtime import refresh_live_ollama_runtime

                refreshed = dict(refresh_live_ollama_runtime() or {})
                retry_api_base_url = str(refreshed.get("api_base_url") or "").strip()
                retry_model = str(refreshed.get("chat_model") or model).strip() or model
                retry_keep_alive = str(refreshed.get("keep_alive") or keep_alive).strip() or keep_alive
                if retry_api_base_url and retry_api_base_url != api_base_url:
                    retry_payload = {
                        **payload,
                        "model": retry_model,
                        "keep_alive": retry_keep_alive,
                    }
                    text = _call_ollama(retry_payload, retry_api_base_url)
                    if text:
                        metadata.update(
                            {
                                "status": "ok",
                                "runtime_refreshed_after_error": True,
                                "model": retry_model,
                            }
                        )
                        return ProviderDraft(text=text, metadata=metadata)
            except Exception as retry_exc:
                metadata["runtime_retry_error_type"] = retry_exc.__class__.__name__

            metadata["runtime_unavailable"] = True
            return _deterministic_runtime_fallback(
                request,
                context,
                evidence,
                workflow,
                metadata,
            )
