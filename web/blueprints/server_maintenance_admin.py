"""Pannello Superadmin per server e manutenzione storage."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from web.blueprints.admin import superadmin_required
from web.services.piattaforma_shell_runtime import render_piattaforma_shell
from web.services.server_maintenance_surface import (
    build_server_maintenance_surface,
)


server_maintenance_admin = Blueprint(
    "server_maintenance_admin",
    __name__,
    url_prefix="/admin/server-manutenzione",
)


def _radice_dati():
    from pathlib import Path

    grezzo = (
        current_app.config.get("PCT_DATA_ROOT")
        or current_app.config.get("DATA_ROOT")
        or "/data"
    )
    return Path(str(grezzo)).expanduser()


@server_maintenance_admin.get("")
@superadmin_required
def dashboard():
    return render_piattaforma_shell("server-manutenzione", "Server e manutenzione")


@server_maintenance_admin.get("/api")
@superadmin_required
def api_dashboard():
    return jsonify(build_server_maintenance_surface())
