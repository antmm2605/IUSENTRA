"""Cache Redis con fallback in memoria per sviluppo e CI."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheStatus:
    ok: bool
    backend: str
    message: str = ""


class CacheClient:
    def __init__(self, redis_url: str = "", *, default_ttl: int = 300) -> None:
        self.redis_url = redis_url
        self.default_ttl = max(1, int(default_ttl or 300))
        self._lock = Lock()
        self._memory: dict[str, tuple[float, str]] = {}
        self._redis = self._connect_redis(redis_url)

    @staticmethod
    def _connect_redis(redis_url: str):
        if not redis_url:
            return None
        try:
            import redis

            client = redis.Redis.from_url(redis_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            return client
        except Exception:
            return None

    @property
    def backend(self) -> str:
        return "redis" if self._redis is not None else "memory"

    def get(self, key: str) -> Any | None:
        if self._redis is not None:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        now = time.time()
        with self._lock:
            item = self._memory.get(key)
            if not item:
                return None
            expires_at, raw = item
            if expires_at < now:
                self._memory.pop(key, None)
                return None
        return json.loads(raw)

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        raw = json.dumps(value, ensure_ascii=False, default=str)
        seconds = max(1, int(ttl or self.default_ttl))
        if self._redis is not None:
            self._redis.setex(key, seconds, raw)
            return
        with self._lock:
            self._memory[key] = (time.time() + seconds, raw)

    def delete(self, key: str) -> None:
        if self._redis is not None:
            self._redis.delete(key)
            return
        with self._lock:
            self._memory.pop(key, None)

    def status(self) -> CacheStatus:
        if self._redis is None:
            return CacheStatus(ok=True, backend="memory", message="Redis non disponibile: fallback in memoria")
        try:
            self._redis.ping()
            return CacheStatus(ok=True, backend="redis")
        except Exception as exc:
            return CacheStatus(ok=False, backend="redis", message=str(exc))
