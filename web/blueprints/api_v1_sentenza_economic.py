"""API JSON App V2 per il Controllo Economico Sentenze (studio-side, avvio manuale).

Endpoint governati: auth di sessione (o API key) + guardia backend-security. Il
feature flag `features.sentenzaEconomicControl` è verificato nel runtime (fail-closed).
Nessun `tenant_id`/path dal client: tutto risolto server-side.
"""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import Blueprint, g, jsonify, request

from web.services.backend_security import (
    backend_control_violations_for_request,
    backend_security_error_response,
)
from web.services.sentenza_economic_runtime import (
    analyze_fascicolo_document,
    build_sentenza_economic_payload,
    confirm_economic_action,
)
from web.services.tenant_api_auth import api_key_valid_for_request


api_v1_sentenza_economic = Blueprint("api_v1_sentenza_economic", __name__)


def _json_body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return dict(payload) if isinstance(payload, dict) else {}


def _status_for(payload: dict[str, Any]) -> int:
    if payload.get("ok", False):
        return 200
    return {
        "unauthorized": 401,
        "forbidden": 403,
        "feature_disabled": 403,
        "tenant_context_required": 409,
        "not_found": 404,
        "validation_error": 422,
    }.get(str(payload.get("code") or ""), 400)


def _json(payload: dict[str, Any]):
    return jsonify(payload), _status_for(payload)


def _studio_auth_required(func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if g.get("utente_corrente") or api_key_valid_for_request():
            return func(*args, **kwargs)
        return jsonify({"ok": False, "code": "unauthorized", "message": "Autenticazione richiesta."}), 401

    return wrapper


@api_v1_sentenza_economic.before_request
def _backend_security_guard():
    violations = backend_control_violations_for_request(request)
    if violations:
        return backend_security_error_response(violations)
    return None


@api_v1_sentenza_economic.get("")
@api_v1_sentenza_economic.get("/")
@_studio_auth_required
def sentenza_economic_list():
    return _json(build_sentenza_economic_payload(str(request.args.get("fascicoloId") or "")))


@api_v1_sentenza_economic.post("/analyze")
@_studio_auth_required
def sentenza_economic_analyze():
    return _json(analyze_fascicolo_document(_json_body()))


@api_v1_sentenza_economic.post("/confirm")
@_studio_auth_required
def sentenza_economic_confirm():
    return _json(confirm_economic_action(_json_body()))
