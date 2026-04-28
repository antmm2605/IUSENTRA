"""Security headers e CSP configurabili."""

from __future__ import annotations

from flask import Flask, Response


def apply_security_headers(response: Response, app: Flask) -> Response:
    if not app.config.get("SECURITY_HEADERS_ENABLED", app.config.get("ENABLE_SECURITY_HEADERS", True)):
        return response
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    csp_header = "Content-Security-Policy-Report-Only" if app.config.get("CSP_REPORT_ONLY") else "Content-Security-Policy"
    response.headers.setdefault(csp_header, build_csp(app))
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def build_csp(app: Flask | None = None) -> str:
    testing = bool(app and app.config.get("TESTING"))
    script_src = "'self' 'unsafe-inline'" if testing else "'self' 'unsafe-inline'"
    return "; ".join(
        [
            "default-src 'self'",
            f"script-src {script_src}",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            "connect-src 'self' http://127.0.0.1:* http://localhost:*",
            "frame-ancestors 'self'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
    )
