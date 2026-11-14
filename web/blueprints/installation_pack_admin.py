from __future__ import annotations

import json
from functools import wraps
from typing import Any

from flask import Blueprint, abort, current_app, g, jsonify, request

from web.services.installation_pack_surface import build_installation_pack_surface
from web.services.piattaforma_shell_runtime import render_piattaforma_shell


installation_pack_admin = Blueprint(
    "installation_pack_admin",
    __name__,
    url_prefix="/admin/installazione-pack",
)


def _richiedi_superadmin() -> None:
    utente = getattr(g, "utente_corrente", None)
    if not utente or not getattr(utente, "is_superadmin", False):
        abort(403)


def superadmin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _richiedi_superadmin()
        return fn(*args, **kwargs)

    return wrapper


def _admin_json_response(payload: Any):
    return current_app.response_class(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        mimetype="application/json",
    )


@installation_pack_admin.route("/")
@superadmin_required
def dashboard():
    return render_piattaforma_shell("installazione-pack", "Pacchetto di installazione")


@installation_pack_admin.route("/api")
@superadmin_required
def api_dashboard():
    try:
        payload = build_installation_pack_surface(selected_slug=request.args.get("slug", ""))
        return _admin_json_response(payload)
    except Exception as exc:  # pragma: no cover - difensivo UI
        current_app.logger.exception("Errore API pack installazione: %s", exc)
        return jsonify({"ok": False, "message": "Pack installazione non disponibili."}), 200
