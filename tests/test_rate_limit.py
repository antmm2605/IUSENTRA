from __future__ import annotations

from flask import Flask

from core.security.rate_limit import InMemoryRateLimiter, parse_rule, register_rate_limiter


def test_parse_rate_limit_rule() -> None:
    rule = parse_rule("10/minute")
    assert rule.max_requests == 10
    assert rule.window_seconds == 60


def test_in_memory_rate_limiter_blocks_after_limit() -> None:
    limiter = InMemoryRateLimiter()
    rule = parse_rule("1/minute")
    assert limiter.allow("ip:endpoint", rule)
    assert not limiter.allow("ip:endpoint", rule)


def test_register_rate_limiter_protects_api_route() -> None:
    app = Flask(__name__)
    app.config.update(RATELIMIT_ENABLED=True, RATELIMIT_DEFAULT="1/minute", RATELIMIT_STORAGE_URI="memory://")
    register_rate_limiter(app)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    client = app.test_client()
    assert client.get("/api/ping").status_code == 200
    assert client.get("/api/ping").status_code == 429
