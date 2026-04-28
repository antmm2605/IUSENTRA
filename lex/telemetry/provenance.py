"""Envelope di provenienza per le risposte Lex."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Any


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        metadata = dict(item.get("metadata") or {})
        return {
            "source_type": item.get("source_type") or metadata.get("source_type") or "",
            "source_id": item.get("source_id") or metadata.get("source_id") or "",
            "title": item.get("title") or "",
            "hash": _sha256(item.get("content") or item.get("excerpt") or ""),
            "official_url": item.get("official_url") or metadata.get("official_url") or metadata.get("url") or "",
        }
    metadata = dict(getattr(item, "metadata", {}) or {})
    return {
        "source_type": getattr(item, "source_type", "") or metadata.get("source_type") or "",
        "source_id": getattr(item, "source_id", "") or metadata.get("source_id") or "",
        "title": getattr(item, "title", "") or "",
        "hash": _sha256(getattr(item, "content", "") or getattr(item, "excerpt", "")),
        "official_url": getattr(item, "official_url", "") or metadata.get("official_url") or metadata.get("url") or "",
    }


def _signature_key() -> str:
    return (
        os.environ.get("LEX_PROVENANCE_HMAC_KEY")
        or os.environ.get("AUDIT_HMAC_KEY")
        or os.environ.get("SECRET_KEY")
        or ""
    )


def build_provenance_envelope(
    *,
    query: str,
    answer: str,
    workflow: str,
    provider_metadata: dict[str, Any] | None = None,
    evidence_items: list[Any] | None = None,
    citations: list[Any] | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Costruisce un envelope machine-readable per audit e replay."""

    items = [_item_to_dict(item) for item in list(evidence_items or [])]
    citation_rows = [_item_to_dict(item) for item in list(citations or [])]
    envelope: dict[str, Any] = {
        "schema_version": "lex.provenance.v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ai_generated": True,
        "human_review_required": workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"},
        "workflow": workflow,
        "query_hash": _sha256(query),
        "answer_hash": _sha256(answer),
        "evidence": items,
        "citations": citation_rows,
        "provider": dict(provider_metadata or {}),
        "parameters": dict(parameters or {}),
    }
    envelope["evidence_hash"] = _sha256(items)
    key = _signature_key()
    if key:
        unsigned = _stable_json(envelope)
        envelope["signature"] = hmac.new(key.encode("utf-8"), unsigned.encode("utf-8"), hashlib.sha256).hexdigest()
        envelope["signature_alg"] = "HMAC-SHA256"
    else:
        envelope["signature"] = ""
        envelope["signature_alg"] = ""
    return envelope
