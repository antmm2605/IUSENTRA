from __future__ import annotations

import hashlib
import json
import os
import time
from copy import deepcopy
from threading import Lock
from typing import Any


def _resolve_cache_ttl_seconds() -> int:
    raw = str(os.getenv("LEX_RETRIEVAL_CACHE_TTL_SECONDS", "") or "").strip()
    try:
        ttl = int(float(raw or 300))
    except (TypeError, ValueError):
        ttl = 300
    return max(15, min(3600, ttl))


def _sanitize_for_cache(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {
            str(key): _sanitize_for_cache(item)
            for key, item in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_for_cache(item) for item in value]
    if hasattr(value, "__dict__"):
        return _sanitize_for_cache(vars(value))
    return str(value)


class LexRetrievalCache:
    def __init__(self, *, ttl_seconds: int | None = None) -> None:
        self.ttl_seconds = int(ttl_seconds or _resolve_cache_ttl_seconds())
        self._entries: dict[str, dict[str, Any]] = {}
        self._lock = Lock()

    def build_key(self, request, context, workflow: str) -> str:
        payload = {
            "tenant_id": str(getattr(request, "tenant_id", "") or "").strip(),
            "workflow": str(workflow or "").strip(),
            "intent": str(getattr(request, "intent", "") or "").strip(),
            "query": str(getattr(request, "query", "") or "").strip(),
            "fascicolo_id": str(getattr(request, "fascicolo_id", "") or "").strip(),
            "document_id": str(getattr(request, "document_id", "") or "").strip(),
            "workflow_hint": str(getattr(request, "workflow_hint", "") or "").strip(),
            "allow_external_research": bool(getattr(request, "allow_external_research", True)),
            "require_citations": bool(getattr(request, "require_citations", False)),
            "require_official_sources": bool(getattr(request, "require_official_sources", False)),
            "metadata": _sanitize_for_cache(getattr(request, "metadata", {}) or {}),
            "context": _sanitize_for_cache(context or {}),
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def get(self, key: str) -> dict[str, Any] | None:
        normalized = str(key or "").strip()
        if not normalized:
            return None
        with self._lock:
            row = self._entries.get(normalized)
            if row is None:
                return None
            if float(row.get("expires_at") or 0.0) <= time.monotonic():
                self._entries.pop(normalized, None)
                return None
            return deepcopy(row.get("payload"))

    def set(self, key: str, payload: dict[str, Any]) -> None:
        normalized = str(key or "").strip()
        if not normalized:
            return
        with self._lock:
            self._entries[normalized] = {
                "expires_at": time.monotonic() + self.ttl_seconds,
                "payload": deepcopy(dict(payload or {})),
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.monotonic()
            active = 0
            for key, row in list(self._entries.items()):
                if float(row.get("expires_at") or 0.0) <= now:
                    self._entries.pop(key, None)
                    continue
                active += 1
            return {"entries": active, "ttl_seconds": self.ttl_seconds}


_GLOBAL_RETRIEVAL_CACHE = LexRetrievalCache()


def get_retrieval_cache() -> LexRetrievalCache:
    return _GLOBAL_RETRIEVAL_CACHE


def clear_retrieval_cache() -> None:
    _GLOBAL_RETRIEVAL_CACHE.clear()
