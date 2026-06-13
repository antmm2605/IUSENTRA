from __future__ import annotations

from flask import Flask

from core.security.headers import apply_security_headers


def _csp_sources(csp: str, directive: str) -> set[str]:
    for part in csp.split(";"):
        tokens = part.strip().split()
        if tokens and tokens[0] == directive:
            return set(tokens[1:])
    return set()


def _csp_has_source(csp: str, directive: str, source: str) -> bool:
    return any(token == source for token in _csp_sources(csp, directive))


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

    assert _csp_has_source(csp, "script-src", "https://cdn.jsdelivr.net")
    assert _csp_has_source(csp, "script-src", "https://esm.sh")
    assert _csp_has_source(csp, "style-src", "https://fonts.googleapis.com")
    assert _csp_has_source(csp, "font-src", "https://fonts.gstatic.com")
    assert _csp_has_source(csp, "style-src", "'unsafe-inline'")
    assert _csp_has_source(csp, "script-src", "'unsafe-inline'")


def test_security_headers_can_be_report_only() -> None:
    app = Flask(__name__)
    app.config.update(SECURITY_HEADERS_ENABLED=True, CSP_REPORT_ONLY=True)
    response = apply_security_headers(app.response_class("ok"), app)
    assert "Content-Security-Policy-Report-Only" in response.headers


def test_support_remote_rooms_allow_microphone_and_display_capture() -> None:
    app = Flask(__name__)
    app.config.update(SECURITY_HEADERS_ENABLED=True)

    with app.test_request_context("/support/operatore/sessione-demo"):
        response = apply_security_headers(app.response_class("ok"), app)
    policy = response.headers["Permissions-Policy"]

    assert "camera=(self)" in policy
    assert "microphone=(self)" in policy
    assert "display-capture=(self)" in policy
    assert "local-network-access=(self)" in policy
    assert "local-network=(self)" in policy
    assert "loopback-network=(self)" in policy
    assert "geolocation=()" in policy


def test_regular_pages_allow_studio_media_only_on_same_origin() -> None:
    app = Flask(__name__)
    app.config.update(SECURITY_HEADERS_ENABLED=True)

    with app.test_request_context("/fascicoli"):
        response = apply_security_headers(app.response_class("ok"), app)

    policy = response.headers["Permissions-Policy"]
    assert "camera=(self)" in policy
    assert "microphone=(self)" in policy
    assert "local-network-access=()" in policy
    assert "local-network=()" in policy
    assert "loopback-network=()" in policy
