"""Blueprint admin per crash test operativo e backup blindato."""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from web.blueprints.admin import superadmin_required
from web.services.piattaforma_shell_runtime import render_piattaforma_shell
from web.services.operational_resilience_surface import (
    build_operational_crash_surface,
)


operational_resilience_admin = Blueprint(
    "operational_resilience_admin",
    __name__,
    url_prefix="/admin/crash-test-operativo",
)


def _selected_slug() -> str:
    return str(request.values.get("slug", "") or "").strip().lower()


def _admin_json_response(payload: Any):
    return current_app.response_class(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        mimetype="application/json",
    )


@operational_resilience_admin.get("")
@superadmin_required
def dashboard():
    return render_piattaforma_shell("crash-test", "Crash test operativo")


@operational_resilience_admin.get("/api")
@superadmin_required
def api_dashboard():
    try:
        payload = build_operational_crash_surface(selected_slug=_selected_slug())
        return _admin_json_response(payload)
    except Exception as exc:  # pragma: no cover - difensivo UI
        current_app.logger.exception("Errore API resilienza operativa: %s", exc)
        return jsonify({"ok": False, "message": "Resilienza operativa non disponibile."}), 200
