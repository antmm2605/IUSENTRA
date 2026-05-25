from __future__ import annotations

import sys
import types

from flask import Flask

from core.security.rate_limit import (
    InMemoryRateLimiter,
    _is_rate_limit_exempt_request,
    _redis_storage_available,
    _resolve_storage_uri,
    parse_rule,
    register_rate_limiter,
)


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


def test_register_rate_limiter_exempts_static_assets(tmp_path) -> None:
    (tmp_path / "app.js").write_text("console.log('iusentra')", encoding="utf-8")
    app = Flask(__name__, static_folder=str(tmp_path), static_url_path="/static")
    app.config.update(RATELIMIT_ENABLED=True, RATELIMIT_DEFAULT="1/minute", RATELIMIT_STORAGE_URI="memory://")
    register_rate_limiter(app)

    client = app.test_client()

    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_redis_rate_limit_storage_falls_back_to_memory(monkeypatch) -> None:
    app = Flask(__name__)
    monkeypatch.setattr("core.security.rate_limit._redis_storage_available", lambda uri: False)

    storage_uri = _resolve_storage_uri(app, "redis://127.0.0.1:1/0")

    assert storage_uri == "memory://"


def test_redis_rate_limit_storage_requires_write_probe(monkeypatch) -> None:
    class _Client:
        def ping(self):
            return True

        def set(self, *_args, **_kwargs):
            raise RuntimeError("MISCONF Redis persistence disabled writes")

        def close(self):
            return None

    class _Redis:
        @staticmethod
        def from_url(*_args, **_kwargs):
            return _Client()

    fake_redis = types.SimpleNamespace(Redis=_Redis)
    monkeypatch.setitem(sys.modules, "redis", fake_redis)

    assert _redis_storage_available("redis://localhost:6379/1") is False


def test_register_rate_limiter_configures_fail_open_fallback(monkeypatch) -> None:
    captured: dict[str, object] = {}
    limiter_module = types.ModuleType("flask_limiter")
    util_module = types.ModuleType("flask_limiter.util")

    class _Limiter:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    limiter_module.Limiter = _Limiter
    util_module.get_remote_address = lambda: "127.0.0.1"
    monkeypatch.setitem(sys.modules, "flask_limiter", limiter_module)
    monkeypatch.setitem(sys.modules, "flask_limiter.util", util_module)
    monkeypatch.setattr("core.security.rate_limit._redis_storage_available", lambda uri: True)

    app = Flask(__name__)
    app.config.update(
        RATELIMIT_ENABLED=True,
        RATELIMIT_DEFAULT="10/minute",
        RATELIMIT_STORAGE_URI="redis://127.0.0.1:6379/1",
    )

    register_rate_limiter(app)

    assert captured["swallow_errors"] is True
    assert captured["in_memory_fallback_enabled"] is True
    assert captured["in_memory_fallback"] == ["10/minute"]
    assert captured["default_limits_exempt_when"] is _is_rate_limit_exempt_request
    assert captured["application_limits_exempt_when"] is _is_rate_limit_exempt_request
    with app.test_request_context("/static/react/assets/index.js", method="GET"):
        assert _is_rate_limit_exempt_request() is True
    with app.test_request_context("/api/v1/ui/dashboard", method="GET"):
        assert _is_rate_limit_exempt_request() is False


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
