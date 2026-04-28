"""Rate limiting leggero con Redis opzionale e fallback in memoria."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from flask import Flask, jsonify, request


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


def register_rate_limiter(app: Flask) -> None:
    if not app.config.get("RATELIMIT_ENABLED", False):
        return
    storage_uri = str(app.config.get("RATELIMIT_STORAGE_URI") or app.config.get("REDIS_URL") or "memory://")
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[str(app.config.get("RATELIMIT_DEFAULT") or "120/minute")],
            storage_uri=storage_uri,
        )
        app.extensions["iusentra_rate_limiter_backend"] = "flask-limiter"
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
