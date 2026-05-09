"""Browser security bootstrap for Flask sessions, headers, and CSRF."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import urlparse

from flask import Flask, abort, request, session

from core.security.headers import apply_security_headers as apply_core_security_headers


_INSECURE_SECRET_MARKERS = (
    "dev-secret-pct-2024",
    "changeme",
    "change-me",
    "example",
    "inserisci",
    "placeholder",
)

_CSRF_PROTECTED_ENDPOINTS = {
    "login",
    "login_2fa",
    "logout",
    "profilo",
    "nuovo_utente",
    "modifica_utente",
    "elimina_utente",
    "permessi_utente",
    "admin.esci_impersonazione",
    "api_v1_documenti_ai.upload_documento_ai",
    "api_v1_documenti_ai.cerca_documento_ai",
    "api_v1_documenti_ai.aggiorna_indice_lex",
    "api_v1_documenti_ai.riprova_errori_indice_lex",
    "api_v1_editor_ai.editor_ai_genera",
    "api_v1_editor_ai.editor_ai_proponi_modifiche",
    "api_v1_editor_ai.editor_ai_accetta_modifica",
    "api_v1_editor_ai.editor_ai_rifiuta_modifica",
    "api_v1_editor_ai.editor_ai_export",
    "api_v1_react.utenti_nuovo_crea",
    "api_v1_react.utenti_aggiorna_stato",
    "api_v1_react.utenti_aggiorna_ruolo",
    "api_v1_react.utenti_reset_password",
    "api_v1_react.utenti_aggiorna_profilo",
    "api_v1_react.profili_page_update",
    "api_v1_react.backup_crea",
    "api_v1_react.backup_verifica",
    "api_v1_react.fatturazione_nuova_crea",
    "api_v1_react.fatturazione_aggiorna_stato",
    "api_v1_react.fatturazione_annulla",
    "api_v1_react.fatturazione_segna_pagata",
    "api_v1_react.preventivi_nuovo_crea",
    "api_v1_react.preventivi_conferimento_nuovo_crea",
    "api_v1_react.preventivi_aggiorna_stato",
    "api_v1_react.incassi_pagamenti_registra_incasso",
    "api_v1_react.incassi_pagamenti_aggiorna_stato",
    "api_v1_react.incassi_pagamenti_collega",
    "api_v1_react.incassi_pagamenti_link_pagamento",
    "api_v1_react.compensi_forensi_calcola",
    "api_v1_react.tariffario_calcola_page",
    "api_v1_react.sito_studio_contatto_collega",
    "api_v1_react.sito_studio_prenotazione_stato",
    "api_v1_react.impostazioni_page_update",
    "api_v1_react.impostazioni_page_test",
    "api_v1_react.impostazioni_page_ai_bootstrap",
    "api_v1_react.impostazioni_notifiche_link",
    "api_v1_react.impostazioni_notifiche_invia",
    "api_v1_react.impostazioni_notifiche_promemoria_domani",
    "api_v1_react.impostazioni_calendari_crea_profilo",
    "api_v1_react.impostazioni_calendari_sincronizza",
    "api_v1_react.impostazioni_calendari_stato",
    "api_v1_react.impostazioni_calendari_elimina",
    "api_v1_react.impostazioni_calendari_rigenera_link",
    }

_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _looks_like_placeholder(secret: str, *, testing: bool) -> bool:
    if not secret:
        return True
    lowered = secret.strip().lower()
    if testing:
        return False
    if len(secret.strip()) < 32:
        return True
    return any(marker in lowered for marker in _INSECURE_SECRET_MARKERS)


def _csrf_token_value() -> str:
    token = session.get("_csrf_token", "")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def apply_security_defaults(app: Flask, config: Mapping[str, object] | None = None) -> None:
    """Apply cookie/session defaults and resolve a safe secret key."""

    cfg = dict(config or {})
    testing = _as_bool(cfg.get("TESTING"), default=False)
    configured_secret = str(
        cfg.get("SECRET_KEY")
        or cfg.get("PCT_SECRET_KEY")
        or ""
    ).strip()
    if _looks_like_placeholder(configured_secret, testing=testing):
        configured_secret = secrets.token_hex(32)
        app.config["SECRET_KEY_EPHEMERAL"] = True
    else:
        app.config["SECRET_KEY_EPHEMERAL"] = False

    app.secret_key = configured_secret
    app.config["SECRET_KEY"] = configured_secret
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
    app.config["SESSION_COOKIE_NAME"] = str(
        cfg.get("SESSION_COOKIE_NAME") or "hacs_session"
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = _as_bool(
        cfg.get("PCT_HTTPS"), default=False
    )
    app.config["SESSION_REFRESH_EACH_REQUEST"] = True
    app.config["ENABLE_BROWSER_CSRF"] = _as_bool(
        cfg.get("ENABLE_BROWSER_CSRF"),
        default=not testing,
    )
    app.config["ENABLE_SECURITY_HEADERS"] = _as_bool(
        cfg.get("ENABLE_SECURITY_HEADERS"),
        default=True,
    )


def register_security_runtime(app: Flask) -> None:
    """Register CSRF protection for sensitive routes and security headers."""

    @app.context_processor
    def inject_security_template_context():
        return {"csrf_token": _csrf_token_value()}

    @app.before_request
    def protect_sensitive_post_routes():
        if request.method not in _UNSAFE_METHODS:
            return None
        if not app.config.get("ENABLE_BROWSER_CSRF", True):
            return None
        if not request.endpoint or request.endpoint not in _CSRF_PROTECTED_ENDPOINTS:
            return None

        expected = session.get("_csrf_token", "")
        provided = (
            request.form.get("_csrf_token")
            or request.headers.get("X-CSRF-Token")
            or ""
        )
        if expected and provided and secrets.compare_digest(expected, provided):
            return None
        if _same_origin_request():
            return None
        abort(400, "Richiesta non valida: conferma di sicurezza mancante o non valida.")

    @app.after_request
    def apply_security_headers(response):
        if not app.config.get("ENABLE_SECURITY_HEADERS", True):
            return response
        return apply_core_security_headers(response, app)


def _same_origin_request() -> bool:
    expected = urlparse(request.host_url)
    for header in ("Origin", "Referer"):
        raw = request.headers.get(header, "").strip()
        if not raw:
            continue
        parsed = urlparse(raw)
        if parsed.scheme == expected.scheme and parsed.netloc == expected.netloc:
            return True
    return False
