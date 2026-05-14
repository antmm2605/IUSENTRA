"""Route storiche SIGP non registrate nell'app principale."""

from __future__ import annotations

import json
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, redirect, render_template, request, url_for

from .service import get_sigp_status, prepara_deposito_sigp
from .sync_service import (
    get_sigp_sync_status,
    import_authorized_sigp_payload,
    resolve_sigp_sync_db_path,
)

sigp_bp = Blueprint("sigp", __name__, url_prefix="/sigp")


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def _parse_json_field(value: str, default):
    raw = (value or "").strip()
    if not raw:
        return default
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return default
    return parsed if parsed is not None else default


def _payload_from_form() -> dict:
    return {
        "ufficio": request.form.get("ufficio", "").strip(),
        "ambiente": request.form.get("ambiente", "produzione").strip() or "produzione",
        "procedimento": request.form.get("procedimento", "").strip(),
        "tipo_atto": request.form.get("tipo_atto", "").strip(),
        "difensore": {
            "nome": request.form.get("difensore_nome", "").strip(),
            "codice_fiscale": request.form.get("difensore_cf", "").strip(),
            "pec": request.form.get("difensore_pec", "").strip(),
        },
        "parti": _parse_json_field(request.form.get("parti_json", ""), []),
        "allegati": _parse_json_field(request.form.get("allegati_json", ""), []),
    }


@sigp_bp.get("/")
@_richiedi_login
def index():
    return render_template(
        "sigp/index.html",
        status=get_sigp_status(),
        result=None,
        form_state={},
    )


@sigp_bp.post("/")
@_richiedi_login
def index_post():
    payload = _payload_from_form()
    return render_template(
        "sigp/index.html",
        status=get_sigp_status(),
        result=prepara_deposito_sigp(payload),
        form_state=payload,
    )


@sigp_bp.get("/status")
@_richiedi_login
def status():
    return jsonify({"ok": True, "status": get_sigp_status()})


@sigp_bp.get("/sync/status")
@_richiedi_login
def sync_status():
    return jsonify(get_sigp_sync_status())


@sigp_bp.post("/sync/importa-payload")
@_richiedi_login
def sync_importa_payload():
    try:
        data = request.get_json(silent=True) or {}
        raw_payload = data.get("payload") or data.get("raw_payload") or data
        result = import_authorized_sigp_payload(
            raw_payload=raw_payload,
            db_path=resolve_sigp_sync_db_path(current_app.config),
            fascicolo_locale_id=(data.get("fascicolo_locale_id") or data.get("fascicoloLocaleId")),
        )
        return jsonify(result)
    except Exception as exc:
        current_app.logger.exception("Errore import payload SIGP autorizzato: %s", exc)
        return jsonify({"ok": False, "errore": str(exc)}), 400


@sigp_bp.post("/depositi/prepara")
@_richiedi_login
def prepara_deposito():
    data = request.get_json(silent=True) or {}
    result = prepara_deposito_sigp(data)
    return jsonify(result), 200 if result.get("ok") else 400
