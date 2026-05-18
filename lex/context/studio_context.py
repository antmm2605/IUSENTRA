"""Bridge di contesto studio posseduti dal package Lex."""

from __future__ import annotations

from typing import Any

from web.services.assistente_studio_context import (
    build_lex_studio_context as _build_lex_studio_context,
)
from web.services.assistente_studio_context import (
    warm_lex_studio_context as _warm_lex_studio_context,
)

_FREE_WEB_MODES = {"free", "free_web", "web_libero", "web libero", "ricerca_libera", "ricerca libera", "libera"}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _payload_flag(value: Any) -> bool:
    return value is True or _clean_spaces(value).lower() in {
        "1",
        "true",
        "vero",
        "yes",
        "si",
        "sì",
        "on",
        "enabled",
        "abilitato",
        "attivo",
    }


def _free_web_requested(metadata: dict[str, Any]) -> bool:
    profile = dict(metadata.get("request_profile") or {}) if isinstance(metadata.get("request_profile"), dict) else {}
    source_mode = _clean_spaces(profile.get("source_mode") or metadata.get("source_mode")).lower()
    if source_mode in _FREE_WEB_MODES:
        return True
    return any(
        _payload_flag(metadata.get(key))
        for key in ("free_web_enabled", "force_free_web_search", "manual_free_web_enabled", "free_web")
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
    workflow_hint = str(getattr(request, "workflow_hint", "") or metadata.get("workflow_hint") or "")
    payload = {
        "tenant_id": getattr(request, "tenant_id", ""),
        "workflow_hint": workflow_hint,
        "request_metadata": metadata,
    }
    if _free_web_requested(metadata):
        return {
            **payload,
            "sources": [],
            "citations": [],
            "structured_context": {},
            "prompt_block": "",
            "focus_label": "",
            "focus_topic": "",
            "free_web_enabled": True,
            "source_mode": "free_web",
        }
    question = str(getattr(request, "query", "") or "").strip()
    if not question:
        return _merge_seed_payload(payload, seed_payload)

    # Percorso rapido per lookup dati cliente: solo anagrafica, nessuna cabina
    if workflow_hint == "studio_data_lookup":
        try:
            from lex.tools.studio_data_gateway import find_cliente
            matches = find_cliente(question)
        except Exception:
            matches = []
        rich_payload: dict[str, Any] = {
            "studio": {
                "sources": [
                    {
                        "id": f"cliente:{m.id}",
                        "title": m.nome_completo,
                        "text": m.to_text(),
                        "type": "cliente",
                    }
                    for m in (matches if "matches" in dir() and matches else [])
                ],
            },
            "studio_data_lookup": True,
            "studio_data_lookup_query": question,
            "studio_data_lookup_matches": len(matches) if "matches" in dir() else 0,
        }
        rich_payload = _merge_seed_payload(rich_payload, seed_payload)
        rich_payload.setdefault("tenant_id", payload["tenant_id"])
        rich_payload.setdefault("workflow_hint", workflow_hint)
        rich_payload.setdefault("request_metadata", metadata)
        return rich_payload

    mode = str(metadata.get("mode") or "chat").strip() or "chat"
    messages = list(metadata.get("messages") or [])
    try:
        rich_payload = dict(_build_lex_studio_context(question, mode=mode, messages=messages) or {})
    except Exception:
        rich_payload = {}

    rich_payload = _merge_seed_payload(rich_payload, seed_payload)
    rich_payload.setdefault("tenant_id", payload["tenant_id"])
    rich_payload.setdefault("workflow_hint", workflow_hint)
    rich_payload.setdefault("request_metadata", metadata)
    return rich_payload
