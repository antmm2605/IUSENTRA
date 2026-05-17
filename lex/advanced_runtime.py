"""Governance snapshot for advanced Lex AI capabilities.

This module is intentionally configuration-only: it tells operators which
advanced capabilities are available, enabled, blocked or still to measure
without starting heavyweight runtimes as a side effect.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


TRUTHY_VALUES = {"1", "true", "yes", "si", "on", "enabled"}


def _truthy(value: str | None, *, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in TRUTHY_VALUES


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return default


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.getenv(name, "") or "").strip() or default)
    except ValueError:
        return default
    return min(max(value, minimum), maximum)


def _status_payload(
    *,
    status: str,
    label: str,
    enabled: bool,
    operator_message: str,
    next_action: str,
    measurement_required: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "status": status,
        "status_label": label,
        "enabled": enabled,
        "operator_message": operator_message,
        "next_action": next_action,
        "measurement_required": measurement_required,
        **extra,
    }


def _external_allowed() -> bool:
    return _truthy(os.getenv("LEX_EXTERNAL_ALLOWED")) or _truthy(
        os.getenv("IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED")
    )


def _build_mtp_status() -> dict[str, Any]:
    engine = _env_first("IUSENTRA_AI_SERVING_ENGINE", "LEX_AI_SERVING_ENGINE", default="ollama").lower()
    mode = _env_first("IUSENTRA_AI_SPECULATIVE_MODE", "LEX_AI_SPECULATIVE_MODE", default="off").lower()
    draft_model = _env_first("IUSENTRA_AI_SPECULATIVE_DRAFT_MODEL", "LEX_AI_SPECULATIVE_DRAFT_MODEL")
    enabled = mode not in {"", "off", "disabled", "none", "0"}
    compatible = engine in {"vllm", "sglang"}
    if not enabled:
        status = _status_payload(
            status="disabled",
            label="Non attivo",
            enabled=False,
            operator_message="La decodifica speculativa non e' attiva: il serving resta sul profilo corrente.",
            next_action="Attivare solo su vLLM o SGLang dopo benchmark sul carico IUSENTRA.",
            engine=engine,
            mode=mode,
            draft_model=draft_model,
        )
    elif not compatible:
        status = _status_payload(
            status="blocked",
            label="Serving non compatibile",
            enabled=True,
            operator_message="MTP o decodifica speculativa sono richiesti, ma il serving configurato non li governa in modo misurabile.",
            next_action="Portare il serving su vLLM o SGLang, poi misurare throughput e latenza prima del cutover.",
            engine=engine,
            mode=mode,
            draft_model=draft_model,
        )
    else:
        status = _status_payload(
            status="ready_to_measure",
            label="Pronto da misurare",
            enabled=True,
            operator_message="Il serving dichiarato supporta la fase di prova: non va promosso senza benchmark comparativo.",
            next_action="Eseguire prova A/B su query Lex reali: primo token, token/sec, p95, errori e qualita' risposte.",
            measurement_required=True,
            engine=engine,
            mode=mode,
            draft_model=draft_model,
        )
    status["references"] = [
        "vLLM MTP",
        "SGLang speculative decoding",
        "SpecDecode-Bench",
    ]
    return status


def _build_llm_wiki_status() -> dict[str, Any]:
    enabled = _truthy(os.getenv("IUSENTRA_LLM_WIKI_ENABLED"))
    root = _env_first("IUSENTRA_LLM_WIKI_ROOT", default="data/intelligence/llm_wiki")
    root_path = Path(root)
    has_index = root_path.exists() and any(root_path.glob("**/*.md"))
    if not enabled:
        payload = _status_payload(
            status="disabled",
            label="Non attivo",
            enabled=False,
            operator_message="LLM Wiki non sostituisce il RAG: resta disponibile come livello compilato sopra le fonti.",
            next_action="Compilare solo fonti ufficiali gia' inventariate e mantenere citazioni verso il dato originale.",
            root=str(root_path),
            compiled_pages=0,
        )
    elif has_index:
        compiled_pages = sum(1 for _ in root_path.glob("**/*.md"))
        payload = _status_payload(
            status="ready_to_evaluate",
            label="Da valutare",
            enabled=True,
            operator_message="Il livello wiki esiste: va confrontato contro RAG e fonti complete prima della promozione.",
            next_action="Eseguire probe di copertura e controllare fatti persi o non citati.",
            measurement_required=True,
            root=str(root_path),
            compiled_pages=compiled_pages,
        )
    else:
        payload = _status_payload(
            status="missing_index",
            label="Da preparare",
            enabled=True,
            operator_message="LLM Wiki e' abilitato ma non esiste ancora un indice compilato leggibile.",
            next_action="Generare pagine Markdown/JSON da Normattiva, GU e fonti ufficiali, poi validarle con probe diagnostici.",
            root=str(root_path),
            compiled_pages=0,
        )
    payload["references"] = ["WiCER / LLM Wiki"]
    return payload


def _build_glm_ocr_status() -> dict[str, Any]:
    enabled = _truthy(os.getenv("IUSENTRA_GLM_OCR_ENABLED"))
    endpoint = _env_first("IUSENTRA_GLM_OCR_ENDPOINT", "GLM_OCR_ENDPOINT")
    provider = _env_first("IUSENTRA_GLM_OCR_PROVIDER", default="self_hosted").lower()
    mode = _env_first("IUSENTRA_GLM_OCR_MODE", default="markdown").lower()
    external_allowed = _external_allowed()
    if not enabled:
        payload = _status_payload(
            status="disabled",
            label="Non attivo",
            enabled=False,
            operator_message="La pipeline OCR resta sul motore corrente; GLM-OCR e' pronto come opzione locale Markdown.",
            next_action="Installare un endpoint self-hosted prima di usarlo su PDF legali.",
            endpoint_configured=bool(endpoint),
            provider=provider,
            mode=mode,
        )
    elif provider in {"maas", "cloud"} and not external_allowed:
        payload = _status_payload(
            status="blocked",
            label="Bloccato da privacy",
            enabled=True,
            operator_message="GLM-OCR cloud e' richiesto, ma i provider esterni non sono autorizzati.",
            next_action="Usare self-hosted locale oppure abilitare provider esterni solo con policy privacy approvata.",
            endpoint_configured=bool(endpoint),
            provider=provider,
            mode=mode,
        )
    elif endpoint:
        payload = _status_payload(
            status="ready_to_test",
            label="Pronto da testare",
            enabled=True,
            operator_message="GLM-OCR ha un endpoint configurato: usarlo prima su campioni PDF legali controllati.",
            next_action="Misurare qualita' Markdown, tabelle, formule, allegati e tempi prima del cutover OCR.",
            measurement_required=True,
            endpoint_configured=True,
            provider=provider,
            mode=mode,
        )
    else:
        payload = _status_payload(
            status="missing_endpoint",
            label="Da configurare",
            enabled=True,
            operator_message="GLM-OCR e' abilitato ma manca l'endpoint locale o self-hosted.",
            next_action="Avviare vLLM/SGLang o SDK server GLM-OCR e impostare IUSENTRA_GLM_OCR_ENDPOINT.",
            endpoint_configured=False,
            provider=provider,
            mode=mode,
        )
    payload["references"] = ["GLM-OCR", "GLM-OCR technical report"]
    return payload


def _build_gemini_embedding_status() -> dict[str, Any]:
    provider = _env_first("IUSENTRA_EMBEDDING_PROVIDER", "PCT_EMBEDDING_PROVIDER", default="local").lower()
    selected = provider in {"gemini", "google", "gemini_embedding_2", "gemini-embedding-2"}
    model = _env_first("IUSENTRA_GEMINI_EMBEDDING_MODEL", "GEMINI_EMBEDDING_MODEL", default="gemini-embedding-001")
    dimensions = _int_env("IUSENTRA_GEMINI_EMBEDDING_DIMENSIONS", 768, minimum=128, maximum=3072)
    api_key_present = bool(_env_first("IUSENTRA_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"))
    external_allowed = _external_allowed()
    if not selected:
        payload = _status_payload(
            status="available_optional",
            label="Opzione disponibile",
            enabled=False,
            operator_message="Gli embeddings restano locali; Gemini Embedding 2 e' disponibile come provider opt-in.",
            next_action="Usarlo per corpus multimodali o multilingua dopo test di qualita' e reindicizzazione completa.",
            provider=provider,
            model=model,
            output_dimensions=dimensions,
            api_key_present=False,
        )
    elif not external_allowed:
        payload = _status_payload(
            status="blocked",
            label="Bloccato da privacy",
            enabled=True,
            operator_message="Gemini Embedding 2 richiede invio contenuti a Google: serve autorizzazione esplicita ai provider esterni.",
            next_action="Impostare LEX_EXTERNAL_ALLOWED=1 solo per studi/corpora autorizzati e non sensibili.",
            provider="gemini",
            model=model,
            output_dimensions=dimensions,
            api_key_present=api_key_present,
        )
    elif not api_key_present:
        payload = _status_payload(
            status="missing_credentials",
            label="Credenziali mancanti",
            enabled=True,
            operator_message="Gemini Embedding 2 e' selezionato ma manca la chiave API.",
            next_action="Configurare GEMINI_API_KEY o IUSENTRA_GEMINI_API_KEY e ripetere un test su campione.",
            provider="gemini",
            model=model,
            output_dimensions=dimensions,
            api_key_present=False,
        )
    else:
        payload = _status_payload(
            status="ready_to_measure",
            label="Pronto da misurare",
            enabled=True,
            operator_message="Gemini Embedding 2 e' configurato: usare solo dopo reindicizzazione completa dello stesso corpus.",
            next_action="Misurare recall@k, precisione, latenza, costo e spazio; non mischiare vettori con embedding precedenti.",
            measurement_required=True,
            provider="gemini",
            model=model,
            output_dimensions=dimensions,
            api_key_present=True,
        )
    payload["requires_full_reembedding"] = selected
    payload["references"] = ["Gemini Embedding 2", "Gemini API embeddings"]
    return payload


def build_advanced_ai_capabilities() -> dict[str, Any]:
    capabilities = {
        "mtp_serving": _build_mtp_status(),
        "llm_wiki": _build_llm_wiki_status(),
        "glm_ocr": _build_glm_ocr_status(),
        "gemini_embedding_2": _build_gemini_embedding_status(),
    }
    enabled = [name for name, item in capabilities.items() if bool(item.get("enabled"))]
    blocked = [
        name
        for name, item in capabilities.items()
        if str(item.get("status") or "") in {"blocked", "missing_credentials", "missing_endpoint", "missing_index"}
        and bool(item.get("enabled"))
    ]
    to_measure = [
        name
        for name, item in capabilities.items()
        if bool(item.get("measurement_required"))
        and str(item.get("status") or "") in {"ready_to_measure", "ready_to_test", "ready_to_evaluate"}
    ]
    return {
        "ok": not blocked,
        "enabled": enabled,
        "blocked": blocked,
        "to_measure": to_measure,
        "capabilities": capabilities,
    }


__all__ = ["build_advanced_ai_capabilities"]
