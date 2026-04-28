from __future__ import annotations

from flask import Flask

from core.security.rate_limit import InMemoryRateLimiter, _resolve_storage_uri, parse_rule, register_rate_limiter


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


def test_redis_rate_limit_storage_falls_back_to_memory(monkeypatch) -> None:
    app = Flask(__name__)
    monkeypatch.setattr("core.security.rate_limit._redis_storage_available", lambda uri: False)

    storage_uri = _resolve_storage_uri(app, "redis://127.0.0.1:1/0")

    assert storage_uri == "memory://"


def test_register_rate_limiter_with_unavailable_redis_does_not_break_requests(monkeypatch) -> None:
    app = Flask(__name__)
    app.config.update(
        RATELIMIT_ENABLED=True,
        RATELIMIT_DEFAULT="10/minute",
        RATELIMIT_STORAGE_URI="redis://127.0.0.1:1/0",
    )
    monkeypatch.setattr("core.security.rate_limit._redis_storage_available", lambda uri: False)
    register_rate_limiter(app)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    response = app.test_client().get("/api/ping")

    assert response.status_code == 200
