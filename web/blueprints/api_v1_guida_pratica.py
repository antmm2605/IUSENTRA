"""Endpoint Guida Pratica per codice materia/PST e fascicolo."""

from __future__ import annotations

from typing import Any, Callable

from flask import Blueprint, current_app, g, jsonify, request

from pct.guida_pratica import GuidaPraticaService
from web.services.react_guida_pratica_bridge import (
    build_react_fascicolo_guida_pratica_payload,
    build_react_guida_pratica_catalog_payload,
    build_react_guida_pratica_checklist_payload,
    build_react_guida_pratica_payload,
    guida_pratica_error_payload,
)

try:  # Mantiene il blueprint importabile anche nei test minimali.
    from web.services.tenant_api_auth import api_key_valid_for_request
except Exception:  # pragma: no cover
    def api_key_valid_for_request() -> bool:
        return False


api_v1_guida_pratica = Blueprint("api_v1_guida_pratica", __name__)
api_guida_pratica = Blueprint("api_guida_pratica", __name__)


def _api_key_valida() -> bool:
    return api_key_valid_for_request()


def _authorized() -> bool:
    if g.get("utente_corrente") or _api_key_valida():
        return True
    return False


def _forbidden() -> Any:
    return jsonify({"ok": False, "code": "unauthorized", "message": "Autenticazione richiesta."}), 401


def _session_user_can(permission: str) -> bool:
    if _api_key_valida():
        return True
    utente = g.get("utente_corrente")
    return bool(utente and getattr(utente, "ha_permesso", lambda _permesso: False)(permission))


def _can_read() -> bool:
    return _session_user_can("fascicoli.leggi") or _session_user_can("telematico.leggi") or _session_user_can("ai.usa")


def _core_runtime_func(name: str) -> Callable[..., Any] | None:
    core_runtime = current_app.extensions.get("core_runtime", {}) or {}
    func = core_runtime.get(name)
    return func if callable(func) else None


def _fascicoli_loader() -> Callable[[], Any]:
    loader = _core_runtime_func("get_fascicoli")
    if callable(loader):
        return loader
    from web.helpers import get_fascicoli

    return get_fascicoli


def _service() -> GuidaPraticaService:
    service = current_app.extensions.get("guida_pratica_service")
    if isinstance(service, GuidaPraticaService):
        return service
    service = GuidaPraticaService()
    current_app.extensions["guida_pratica_service"] = service
    return service


def _ensure_read_access() -> Any | None:
    if not _authorized():
        return _forbidden()
    if not _can_read():
        return jsonify({"ok": False, "code": "forbidden", "message": "Permesso non sufficiente per leggere la Guida Pratica."}), 403
    return None


@api_v1_guida_pratica.get("/guida-pratica/catalogo")
def guida_pratica_catalogo():
    denied = _ensure_read_access()
    if denied:
        return denied
    try:
        limit = max(1, min(2000, int(request.args.get("limit", "2000") or 2000)))
    except ValueError:
        limit = 2000
    try:
        return jsonify(
            build_react_guida_pratica_catalog_payload(
                query=str(request.args.get("q", "") or ""),
                coverage=str(request.args.get("coverage", "") or ""),
                limit=limit,
                service=_service(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore catalogo Guida Pratica: %s", exc)
        return jsonify(guida_pratica_error_payload(exc)), 500


@api_v1_guida_pratica.get("/guida-pratica/<codice>")
def guida_pratica_codice(codice: str):
    denied = _ensure_read_access()
    if denied:
        return denied
    try:
        return jsonify(build_react_guida_pratica_payload(codice=codice, service=_service()))
    except Exception as exc:
        current_app.logger.exception("Errore Guida Pratica codice %s: %s", codice, exc)
        return jsonify(guida_pratica_error_payload(exc)), 404


@api_guida_pratica.get("/api/guida/<codice>")
def guida_pratica_rest_codice(codice: str):
    denied = _ensure_read_access()
    if denied:
        return denied
    try:
        return jsonify(build_react_guida_pratica_payload(codice=codice, service=_service()))
    except Exception as exc:
        current_app.logger.exception("Errore Guida Pratica REST codice %s: %s", codice, exc)
        return jsonify(guida_pratica_error_payload(exc)), 404


@api_v1_guida_pratica.post("/guida-pratica/<codice>/checklist")
def guida_pratica_checklist(codice: str):
    denied = _ensure_read_access()
    if denied:
        return denied
    dati = request.get_json(silent=True) or {}
    if not isinstance(dati, dict):
        dati = {}
    try:
        return jsonify(build_react_guida_pratica_checklist_payload(codice=codice, dati=dati, service=_service()))
    except Exception as exc:
        current_app.logger.exception("Errore checklist Guida Pratica codice %s: %s", codice, exc)
        return jsonify(guida_pratica_error_payload(exc)), 400


@api_guida_pratica.post("/api/guida/<codice>/checklist")
def guida_pratica_rest_checklist(codice: str):
    denied = _ensure_read_access()
    if denied:
        return denied
    dati = request.get_json(silent=True) or {}
    if not isinstance(dati, dict):
        dati = {}
    try:
        return jsonify(build_react_guida_pratica_checklist_payload(codice=codice, dati=dati, service=_service()))
    except Exception as exc:
        current_app.logger.exception("Errore checklist Guida Pratica REST codice %s: %s", codice, exc)
        return jsonify(guida_pratica_error_payload(exc)), 400


@api_v1_guida_pratica.get("/fascicoli/<id_fasc>/guida-pratica")
def guida_pratica_fascicolo(id_fasc: str):
    denied = _ensure_read_access()
    if denied:
        return denied
    try:
        return jsonify(
            build_react_fascicolo_guida_pratica_payload(
                get_fascicoli=_fascicoli_loader(),
                id_fasc=id_fasc,
                service=_service(),
            )
        )
    except Exception as exc:
        current_app.logger.exception("Errore Guida Pratica fascicolo %s: %s", id_fasc, exc)
        return jsonify(guida_pratica_error_payload(exc)), 500
