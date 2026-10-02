"""Provider applicativo Ollama posseduto da Lex.

Chiama in modo sincrono il runtime Ollama locale tramite l'HTTP client
configurato. Costruisce il prompt RAG (system prompt + messaggio
"Domanda / [Dati dello studio] / Fonti") entro il budget di contesto
(`lex.providers.prompt_budget`), con i parametri di generazione unici di
`lex.settings.lex_generation_settings()`, esegue la generazione non-streaming e
restituisce la bozza pronta per il passaggio successivo della pipeline Lex.
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from pct.local_ai import OllamaHttpClient

from .base import BaseProvider
from .prompt_budget import (
    build_rag_prompt,
    check_prompt_eval,
    evidence_items as _budget_evidence_items,
    format_evidence_item,
    strip_think,
)
from lex.contracts import ProviderDraft
from lex.prompts.legal_rag_prompt import (
    LEGAL_AI_RESPONSE_CONTRACT,
    LEX_LEGAL_RAG_SYSTEM_PROMPT,
    is_legal_rag_workflow,
)
from lex.settings import lex_generation_settings

logger = logging.getLogger("lex.providers.ollama")


_FALLBACK_SYSTEM_PROMPT = (
    "Sei Lex, assistente legale professionale per uno studio legale italiano. "
    "Rispondi sempre in italiano formale, in modo accurato, sintetico e citando "
    "le evidenze ricevute quando presenti. Non inventare norme, sentenze o "
    "termini: se non hai informazioni sufficienti, segnala esplicitamente i "
    "dati mancanti e suggerisci la verifica presso le fonti ufficiali."
)

_LEGAL_AI_RESPONSE_CONTRACT = LEGAL_AI_RESPONSE_CONTRACT

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
    # Workflow giuridici: una sola stringa fissa (cache del prefisso di Ollama e
    # stesso testo del dataset di fine-tuning).
    if is_legal_rag_workflow(workflow):
        return LEX_LEGAL_RAG_SYSTEM_PROMPT
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
    return _budget_evidence_items(evidence)


def _format_evidence(evidence: Any, limit: int | None = None) -> str:
    """Evidenze nel formato unico "[n] Fonte · art. · URN/ECLI · vigenza · data".

    Senza budget: il budget di contesto si applica in `build_rag_prompt`.
    """
    settings = lex_generation_settings()
    max_items = settings.max_evidence_items if limit is None else int(limit)
    rows: list[str] = []
    for item in _evidence_items(evidence)[:max_items]:
        block, _ = format_evidence_item(len(rows) + 1, item, max_chars=settings.evidence_max_chars)
        if block:
            rows.append(block)
    return "\n\n".join(rows)


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


class _OllamaText(str):
    """Testo della risposta con le statistiche di Ollama (prompt_eval_count, ...)."""

    stats: dict[str, Any]

    def __new__(cls, value: str, stats: dict[str, Any] | None = None):
        obj = super().__new__(cls, value)
        obj.stats = dict(stats or {})
        return obj


def _think_not_supported(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    if response is None or getattr(response, "status_code", None) != 400:
        return False
    try:
        body = str(response.text or "")
    except Exception:
        body = ""
    return "think" in body.lower()


def _call_ollama(payload: dict[str, Any], api_base_url: str, timeout: int | None = None) -> str:
    effective_timeout = int(timeout or lex_generation_settings().timeout_s)
    client = OllamaHttpClient(api_base_url, timeout=effective_timeout)
    kwargs: dict[str, Any] = {
        "messages": list(payload.get("messages") or []),
        "keep_alive": str(payload.get("keep_alive") or "10m"),
        "options": dict(payload.get("options") or {}),
        "timeout": effective_timeout,
    }
    if "think" in payload:
        kwargs["think"] = bool(payload.get("think"))
    model = str(payload.get("model") or "mistral")
    try:
        response = client.chat(model, **kwargs)
    except requests.HTTPError as exc:
        # Modelli senza supporto al ragionamento possono rifiutare il campo
        # "think": si ripete una sola volta senza il campo.
        if "think" not in kwargs or not _think_not_supported(exc):
            raise
        kwargs.pop("think", None)
        response = client.chat(model, **kwargs)
    text = str(((response.get("message") or {}).get("content") or "")).strip()
    stats = {
        key: response.get(key)
        for key in ("prompt_eval_count", "eval_count", "total_duration", "prompt_eval_duration", "eval_duration", "load_duration")
        if response.get(key) is not None
    }
    return _OllamaText(text, stats)


def _model_error_kind(exc: Exception | None) -> str:
    if exc is None:
        return "errore"
    if isinstance(exc, requests.Timeout) or "timeout" in exc.__class__.__name__.lower() or "timed out" in str(exc).lower():
        return "timeout"
    if isinstance(exc, requests.ConnectionError) or "connection" in exc.__class__.__name__.lower():
        return "non_raggiungibile"
    if "circuit" in exc.__class__.__name__.lower():
        return "non_raggiungibile"
    return "errore"


def _model_error_notice(kind: str, timeout_s: int, *, has_content: bool) -> str:
    """Avviso breve in italiano: il modello non ha risposto (mai un fallback silenzioso)."""
    if kind == "timeout":
        head = f"Il modello locale non ha risposto entro {timeout_s} secondi."
    elif kind == "non_raggiungibile":
        head = "Il modello locale non è raggiungibile in questo momento."
    elif kind == "vuoto":
        head = "Il modello locale non ha prodotto una risposta."
    else:
        head = "Il modello locale non ha risposto correttamente."
    if has_content:
        return head + " Di seguito solo quanto ricavato direttamente da dati e fonti, senza elaborazione del modello."
    return head + " Riprova tra poco."


def _deterministic_runtime_fallback(request, context, evidence, workflow, metadata: dict[str, Any]):
    from .deterministic_provider import DeterministicProvider

    draft = DeterministicProvider().generate(request, context, evidence, workflow or "chat")
    deterministic_text = str(getattr(draft, "text", "") or "").strip()
    kind = str(metadata.get("model_error_kind") or "errore")
    timeout_s = int(metadata.get("timeout_s") or lex_generation_settings().timeout_s)
    notice = _model_error_notice(kind, timeout_s, has_content=bool(deterministic_text))
    draft.text = f"{notice}\n\n{deterministic_text}" if deterministic_text else notice
    draft.metadata = {
        **dict(getattr(draft, "metadata", {}) or {}),
        **metadata,
        "provider": "ollama",
        "fallback_provider": "deterministic",
        "status": "fallback_runtime_unavailable",
        "model_error_notice": notice,
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


class _EmptyModelResponse(RuntimeError):
    """Il modello ha risposto senza testo utile (anche dopo la rimozione di <think>)."""


class OllamaProvider(BaseProvider):
    provider_name = "ollama"

    def generate(self, request, context, evidence, workflow):
        workflow_name = workflow or "chat"
        settings = lex_generation_settings()
        system_prompt = _build_system_prompt(workflow_name, context)
        evidence_items = _evidence_items(evidence)
        runtime = _resolve_runtime()
        model = str(runtime.get("chat_model") or "mistral").strip() or "mistral"
        api_base_url = str(runtime.get("api_base_url") or "http://127.0.0.1:11434/api").strip()
        keep_alive = str(runtime.get("keep_alive") or "10m").strip() or "10m"
        metadata: dict[str, Any] = {
            "provider": self.provider_name,
            "model": model,
            "workflow": workflow_name,
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
        if (workflow or "") == "giurisprudenza":
            try:
                from lex.reasoning.case_law_interpreter import build_case_law_context

                case_law_rows = build_case_law_context(evidence_items)
            except Exception:
                case_law_rows = []

        query = str(getattr(request, "query", "") or "").strip()
        plan = build_rag_prompt(
            system_prompt=system_prompt,
            question=query,
            evidence=evidence,
            workflow=workflow_name,
            context=context,
            settings=settings,
        )
        metadata["prompt_budget"] = plan.metadata
        metadata["generation"] = {
            "num_ctx": settings.num_ctx,
            "num_predict": settings.num_predict,
            "temperature": settings.temperature,
            "think": settings.think,
            "timeout_s": settings.timeout_s,
        }
        metadata["timeout_s"] = settings.timeout_s

        payload = {
            "model": model,
            "keep_alive": keep_alive,
            "options": settings.ollama_options(),
            "think": settings.think,
            "messages": plan.messages(),
        }
        if isinstance(evidence, dict) and "evidence_sufficient" in evidence:
            metadata["evidence_sufficient"] = bool(evidence.get("evidence_sufficient"))

        try:
            raw = _call_ollama(payload, api_base_url, timeout=settings.timeout_s)
            metadata["prompt_eval"] = check_prompt_eval(plan.metadata, dict(getattr(raw, "stats", {}) or {}))
            text = strip_think(raw)
            if not text:
                metadata["model_error_kind"] = "vuoto"
                raise _EmptyModelResponse("Nessun contenuto generato dal modello locale.")
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
            if not isinstance(exc, _EmptyModelResponse):
                metadata["model_error_kind"] = _model_error_kind(exc)
            logger.warning(
                "Lex: il modello locale non ha risposto (%s, workflow=%s, modello=%s).",
                metadata.get("model_error_kind"),
                workflow_name,
                model,
            )
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
                    text = strip_think(_call_ollama(retry_payload, retry_api_base_url, timeout=settings.timeout_s))
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
