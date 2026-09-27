"""Security headers e CSP configurabili.

Script: la CSP non ammette ``'unsafe-inline'``. Il browser esegue i file dello
studio e degli host dichiarati e, fra i blocchi ``<script>`` in linea, solo quelli
che portano il nonce della richiesta (``{{ csp_nonce() }}`` nei template). Gli
attributi evento (``onclick=``) non sono più ammessi: i template legacy usano
``data-iu-on`` e ``web/static/js/iu-gestori.js`` (scripts/csp_gestori_legacy.py).

Stili: ``'unsafe-inline'`` resta per ``style-src``: i template legacy e le librerie
di terzi usano attributi ``style``; uno stile non esegue codice. Le immagini
esterne restano limitate a https.

Base: CSP Level 3 (W3C); OWASP Cross Site Scripting Prevention Cheat Sheet.
"""

from __future__ import annotations

import secrets

from flask import Flask, Response, g, has_request_context, request


_SUPPORT_MEDIA_PATH_PREFIXES = ("/support/join/", "/support/operatore/")


def _permissions_policy_for_current_request() -> str:
    if has_request_context() and request.path.startswith(_SUPPORT_MEDIA_PATH_PREFIXES):
        return (
            "camera=(self), microphone=(self), display-capture=(self), "
            "local-network-access=(self), local-network=(self), loopback-network=(self), "
            "geolocation=(), payment=()"
        )
    return (
        "camera=(self), microphone=(self), local-network-access=(self), local-network=(self), "
        "loopback-network=(self), geolocation=(), payment=()"
    )


def csp_nonce() -> str:
    """Il nonce CSP della richiesta corrente (uno per richiesta, generato alla prima lettura)."""
    if not has_request_context():
        return ""
    nonce = getattr(g, "_csp_nonce", "")
    if not nonce:
        nonce = secrets.token_urlsafe(18)
        g._csp_nonce = nonce
    return nonce


SEGNAPOSTO_NONCE = "iuCspNonceSegnaposto0000"


def prepara_nonce_documento_stabile() -> None:
    """Per i documenti con ETag: il template riceve un segnaposto al posto del nonce."""
    if has_request_context():
        g._csp_nonce = SEGNAPOSTO_NONCE


def applica_nonce_documento_stabile(corpo: str, *, segreto: str, seme: str) -> str:
    """Sostituisce il segnaposto con un nonce stabile per (documento, sessione).

    La shell React si rivalida con ETag e 304: con un nonce nuovo a ogni
    richiesta il corpo cambierebbe sempre, e un 304 con un'intestazione CSP
    nuova non combacerebbe più con il corpo che il browser conserva. Il nonce
    è quindi HMAC(segreto, impronta del documento + seme della sessione): non
    prevedibile senza il segreto, diverso per ogni sessione, uguale finché il
    documento non cambia. Il documento non contiene HTML non fidato reso dal
    server (i dati viaggiano come JSON in un blocco non eseguibile).
    """
    import base64
    import hashlib
    import hmac

    impronta = hashlib.sha256(corpo.encode("utf-8")).hexdigest()
    firma = hmac.new(segreto.encode("utf-8"), f"{impronta}|{seme}".encode("utf-8"), hashlib.sha256).digest()
    nonce = base64.urlsafe_b64encode(firma[:18]).decode("ascii")
    if has_request_context():
        g._csp_nonce = nonce
    return corpo.replace(SEGNAPOSTO_NONCE, nonce)


def apply_security_headers(response: Response, app: Flask) -> Response:
    if not app.config.get("SECURITY_HEADERS_ENABLED", app.config.get("ENABLE_SECURITY_HEADERS", True)):
        return response
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", _permissions_policy_for_current_request())
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    csp_header = "Content-Security-Policy-Report-Only" if app.config.get("CSP_REPORT_ONLY") else "Content-Security-Policy"
    response.headers.setdefault(csp_header, build_csp(app, nonce=csp_nonce()))
    if app.config.get("SESSION_COOKIE_SECURE"):
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def build_csp(app: Flask | None = None, *, nonce: str = "") -> str:
    testing = bool(app and app.config.get("TESTING"))
    script_src = (
        "'self' "
        + (f"'nonce-{nonce}' " if nonce else "")
        + "https://cdn.jsdelivr.net "
        "https://esm.sh "
        "https://gateway.sumup.com"
    )
    # Le pagine legacy usano attributi style: uno stile non esegue codice.
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
            # Il widget SumUp del link di pagamento monta i campi carta in iframe del gestore.
            "frame-src 'self' blob: https://gateway.sumup.com",
            "frame-ancestors 'self'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
    )
