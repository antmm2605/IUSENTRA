"""Security headers e CSP configurabili."""

from __future__ import annotations

from flask import Flask, Response, has_request_context, request


_SUPPORT_MEDIA_PATH_PREFIXES = ("/support/join/", "/support/operatore/")


def _permissions_policy_for_current_request() -> str:
    if has_request_context() and request.path.startswith(_SUPPORT_MEDIA_PATH_PREFIXES):
        return (
            "camera=(), microphone=(self), display-capture=(self), "
            "local-network-access=(self), local-network=(self), loopback-network=(self), "
            "geolocation=(), payment=()"
        )
    return (
        "camera=(), microphone=(), local-network-access=(), local-network=(), "
        "loopback-network=(), geolocation=(), payment=()"
    )


def apply_security_headers(response: Response, app: Flask) -> Response:
    if not app.config.get("SECURITY_HEADERS_ENABLED", app.config.get("ENABLE_SECURITY_HEADERS", True)):
        return response
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", _permissions_policy_for_current_request())
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    csp_header = "Content-Security-Policy-Report-Only" if app.config.get("CSP_REPORT_ONLY") else "Content-Security-Policy"
    response.headers.setdefault(csp_header, build_csp(app))
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def build_csp(app: Flask | None = None) -> str:
    testing = bool(app and app.config.get("TESTING"))
    script_src = (
        "'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net "
        "https://esm.sh "
        "https://gateway.sumup.com"
    )
    style_src = (
        "'self' 'unsafe-inline' "
        "https://cdn.jsdelivr.net "
        "https://fonts.googleapis.com "
        "https://esm.sh"
    )
    font_src = "'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com"
    img_src = "'self' data: blob: https:"
    connect_src = (
        "'self' "
        "http://127.0.0.1:* "
        "http://localhost:* "
        "https://cdn.jsdelivr.net "
        "https://esm.sh "
        "https://gateway.sumup.com"
    )
    if testing:
        connect_src += " ws://127.0.0.1:* ws://localhost:*"
    return "; ".join(
        [
            "default-src 'self'",
            f"script-src {script_src}",
            f"style-src {style_src}",
            f"img-src {img_src}",
            f"font-src {font_src}",
            f"connect-src {connect_src}",
            "worker-src 'self' blob: https://cdn.jsdelivr.net",
            "frame-ancestors 'self'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
    )
