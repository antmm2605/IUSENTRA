"""Bridge di contesto studio posseduti dal package Lex."""

from __future__ import annotations

from typing import Any

from web.services.assistente_studio_context import (
    build_lex_studio_context as _build_lex_studio_context,
)
from web.services.assistente_studio_context import (
    warm_lex_studio_context as _warm_lex_studio_context,
)


def _merge_seed_payload(live_payload: dict[str, Any], seed_payload: dict[str, Any]) -> dict[str, Any]:
    merged = dict(live_payload or {})
    for key, value in dict(seed_payload or {}).items():
        if isinstance(value, dict):
            if not value and key in merged:
                continue
            base = dict(merged.get(key) or {}) if isinstance(merged.get(key), dict) else {}
            base.update(value)
            merged[key] = base
            continue
        if isinstance(value, list):
            if not value and key in merged:
                continue
            merged[key] = list(value)
            continue
        if value in {"", None} and key in merged:
            continue
        merged[key] = value
    return merged


def build_lex_studio_context(*args, **kwargs) -> dict[str, Any]:
    """Espone il builder storico sotto ownership lessicale di ``lex/``."""

    return dict(_build_lex_studio_context(*args, **kwargs) or {})


def warm_lex_studio_context(*args, **kwargs) -> dict[str, Any]:
    """Pre-riscalda il contesto studio per i flussi Lex."""

    return dict(_warm_lex_studio_context(*args, **kwargs) or {})


def build_studio_context(request) -> dict[str, Any]:
    """Costruisce un contesto studio ricco per il workflow applicativo puro.

    Fuori da Flask o in ambienti di test il builder storico puo' non essere
    disponibile: in quel caso Lex degrada su un payload minimo ma coerente.
    """

    metadata = dict(getattr(request, "metadata", {}) or {})
    seed_payload = dict(metadata.get("studio_context_seed") or {})
    payload = {
        "tenant_id": getattr(request, "tenant_id", ""),
        "workflow_hint": getattr(request, "workflow_hint", "") or "",
        "request_metadata": metadata,
    }
    question = str(getattr(request, "query", "") or "").strip()
    if not question:
        return _merge_seed_payload(payload, seed_payload)

    mode = str(metadata.get("mode") or "chat").strip() or "chat"
    messages = list(metadata.get("messages") or [])
    try:
        rich_payload = dict(_build_lex_studio_context(question, mode=mode, messages=messages) or {})
    except Exception:
        rich_payload = {}

    rich_payload = _merge_seed_payload(rich_payload, seed_payload)
    rich_payload.setdefault("tenant_id", payload["tenant_id"])
    rich_payload.setdefault("workflow_hint", payload["workflow_hint"])
    rich_payload.setdefault("request_metadata", metadata)
    return rich_payload
