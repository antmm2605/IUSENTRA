"""Rate limiting leggero con Redis opzionale e fallback in memoria."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from flask import Flask, jsonify, request

_REDIS_STORAGE_PREFIXES = ("redis://", "rediss://", "unix://")


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, rule: RateLimitRule) -> bool:
        now = time.time()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - rule.window_seconds:
                hits.popleft()
            if len(hits) >= rule.max_requests:
                return False
            hits.append(now)
            return True


def parse_rule(value: str) -> RateLimitRule:
    raw = str(value or "120/minute").strip().lower()
    number, _, unit = raw.partition("/")
    amount = int(number or 120)
    seconds = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}.get(unit.rstrip("s"), 60)
    return RateLimitRule(amount, seconds)


def _redis_storage_available(storage_uri: str) -> bool:
    try:
        import redis

        client = redis.Redis.from_url(storage_uri, socket_connect_timeout=0.25, socket_timeout=0.25)
        try:
            client.ping()
        finally:
            try:
                client.close()
            except Exception:
                pass
        return True
    except Exception:
        return False


def _resolve_storage_uri(app: Flask, storage_uri: str) -> str:
    if not storage_uri.lower().startswith(_REDIS_STORAGE_PREFIXES):
        return storage_uri
    if _redis_storage_available(storage_uri):
        return storage_uri
    app.logger.warning(
        "Redis rate limiter non raggiungibile (%s): uso storage memory:// per evitare blocchi applicativi.",
        storage_uri,
    )
    return "memory://"


def register_rate_limiter(app: Flask) -> None:
    if not app.config.get("RATELIMIT_ENABLED", False):
        return
    storage_uri = str(app.config.get("RATELIMIT_STORAGE_URI") or app.config.get("REDIS_URL") or "memory://")
    storage_uri = _resolve_storage_uri(app, storage_uri)
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[str(app.config.get("RATELIMIT_DEFAULT") or "120/minute")],
            storage_uri=storage_uri,
        )
        app.extensions["iusentra_rate_limiter_backend"] = f"flask-limiter:{storage_uri}"
        return
    except Exception as exc:
        app.logger.warning("Flask-Limiter non disponibile, uso fallback in memoria: %s", exc)

    limiter = InMemoryRateLimiter()
    default_rule = parse_rule(str(app.config.get("RATELIMIT_DEFAULT") or "120/minute"))
    strict_rule = parse_rule("10/minute")
    app.extensions["iusentra_rate_limiter_backend"] = "memory"

    @app.before_request
    def _apply_rate_limit():
        endpoint = request.endpoint or ""
        rule = strict_rule if any(token in endpoint for token in ("login", "upload", "assistente", "api_job")) else default_rule
        identity = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
        key = f"{identity}:{endpoint}:{request.method}"
        if limiter.allow(key, rule):
            return None
        if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
            return jsonify({"ok": False, "errore": "Troppe richieste: riprova tra poco."}), 429
        return "Troppe richieste: riprova tra poco.", 429
