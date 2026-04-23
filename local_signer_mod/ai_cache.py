from __future__ import annotations

import hashlib
import json
import time
from typing import Any


class TimedResultCache:
    def __init__(self, ttl_seconds: int = 30, max_items: int = 128) -> None:
        self.ttl_seconds = max(int(ttl_seconds), 1)
        self.max_items = max(int(max_items), 1)
        self._items: dict[str, tuple[float, Any]] = {}

    def _key(self, namespace: str, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        digest = hashlib.sha256(f"{namespace}:{serialized}".encode("utf-8")).hexdigest()
        return digest

    def get(self, namespace: str, payload: dict[str, Any]) -> Any | None:
        key = self._key(namespace, payload)
        entry = self._items.get(key)
        if not entry:
            return None
        created_at, value = entry
        if (time.time() - created_at) > self.ttl_seconds:
            self._items.pop(key, None)
            return None
        return value

    def set(self, namespace: str, payload: dict[str, Any], value: Any) -> Any:
        if len(self._items) >= self.max_items:
            oldest_key = min(self._items, key=lambda item: self._items[item][0])
            self._items.pop(oldest_key, None)
        key = self._key(namespace, payload)
        self._items[key] = (time.time(), value)
        return value

    def get_or_set(self, namespace: str, payload: dict[str, Any], factory):
        cached = self.get(namespace, payload)
        if cached is not None:
            return cached
        value = factory()
        return self.set(namespace, payload, value)
