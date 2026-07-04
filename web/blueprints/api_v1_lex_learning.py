"""API JSON read-only per la superficie "Apprendimento Lex".

Un solo endpoint (`GET /api/v1/ui/lex-learning`) dietro tre guardie:
autenticazione, feature flag `lex.autonomousLearning`, permesso `ai.usa` —
stesso skeleton fail-closed di `api_v1_legal_skills`. Nessuna azione
dispositiva: la pagina ispeziona la memoria del ciclo autonomo e rimanda
alla console Pianificazioni per l'attivazione del job notturno.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.feature_flags import feature_disabled_response, is_feature_enabled
from web.services.react_lex_learning_bridge import build_react_lex_learning_payload
from web.services.tenant_api_auth import api_key_valid_for_request

api_v1_lex_learning = Blueprint("api_v1_lex_learning", __name__, url_prefix="/api/v1/ui")

FEATURE_FLAG = "lex.autonomousLearning"
PERMESSO_LETTURA = "ai.usa"


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


def _audit_event(action: str, resource_type: str = "", resource_id: str = "", details: str = "") -> None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    audit = core_runtime.get("audit")
    if callable(audit):
        audit(action, resource_type, resource_id, details)


def _has_permission(permission: str) -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)(permission))


def _require_auth(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or _api_key_valida():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "code": "unauthorized", "message": "Autenticazione richiesta."}), 401

    return wrapper


def _require_feature(flag_key: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if is_feature_enabled(flag_key):
                return func(*args, **kwargs)
            return feature_disabled_response(flag_key)

        return wrapper

    return decorator


def _require_permission(permission: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if _has_permission(permission):
                return func(*args, **kwargs)
            _audit_event("policy_denied.lex_learning", "permission", permission, "Permesso Lex mancante.")
            return jsonify({"ok": False, "code": "permission_denied", "message": "Permesso non disponibile."}), 403

        return wrapper

    return decorator


@api_v1_lex_learning.before_request
def _backend_security_guard():
    if not (g.get("utente_corrente") or _api_key_valida()):
        return None
    violations = backend_control_violations_for_request(request)
    if not violations:
        return None
    keys = ",".join(sorted({violation.key for violation in violations}))
    _audit_event("policy_denied.backend_security", "lex_learning", request.path, f"Parametri riservati bloccati: {keys}.")
    return backend_security_error_response(violations)


@api_v1_lex_learning.get("/lex-learning")
@_require_auth
@_require_feature(FEATURE_FLAG)
@_require_permission(PERMESSO_LETTURA)
def lex_learning_payload():
    try:
        return jsonify(build_react_lex_learning_payload(current_app.config))
    except Exception as exc:  # difesa: la superficie non deve mai propagare 500
        current_app.logger.exception("Errore payload lex-learning: %s", exc)
        return jsonify({"ok": False, "code": "internal_error", "message": "Dati non disponibili al momento."}), 200


__all__ = ["api_v1_lex_learning"]
