from __future__ import annotations

from flask import Flask

from core.security.headers import apply_security_headers


def test_security_headers_include_csp_and_hardening_headers() -> None:
    app = Flask(__name__)
    app.config.update(SECURITY_HEADERS_ENABLED=True, CSP_REPORT_ONLY=False, SESSION_COOKIE_SECURE=True)
    response = app.response_class("ok")

    hardened = apply_security_headers(response, app)

    assert hardened.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in hardened.headers
    assert "Strict-Transport-Security" in hardened.headers
    assert hardened.headers["X-Frame-Options"] == "SAMEORIGIN"


def test_csp_allows_governed_ui_assets_without_breaking_layout() -> None:
    app = Flask(__name__)
    app.config.update(SECURITY_HEADERS_ENABLED=True)
    response = apply_security_headers(app.response_class("ok"), app)
    csp = response.headers["Content-Security-Policy"]

    assert "https://cdn.jsdelivr.net" in csp
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp
    assert "https://esm.sh" in csp
    assert "style-src 'self' 'unsafe-inline'" in csp
    assert "script-src 'self' 'unsafe-inline'" in csp


def test_security_headers_can_be_report_only() -> None:
    app = Flask(__name__)
    app.config.update(SECURITY_HEADERS_ENABLED=True, CSP_REPORT_ONLY=True)
    response = apply_security_headers(app.response_class("ok"), app)
    assert "Content-Security-Policy-Report-Only" in response.headers
