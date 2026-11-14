"""Console superadmin per pianificazioni, cronjob e agenti delegati."""

from __future__ import annotations

from flask import Blueprint, redirect, url_for, g

from web.blueprints.admin import superadmin_required
from web.services.piattaforma_shell_runtime import render_piattaforma_shell
from web.services.scheduler_admin_surface import (
    build_scheduler_admin_surface,
)
from web.services.security_redaction import redacted_json_response


scheduler_admin = Blueprint("scheduler_admin", __name__)


def _username() -> str:
    user = getattr(g, "utente_corrente", None)
    return str(getattr(user, "username", "") or "superadmin")


@scheduler_admin.get("/admin/pianificazioni")
@superadmin_required
def dashboard():
    return render_piattaforma_shell("pianificazioni", "Pianificazioni")


@scheduler_admin.get("/admin/cronjob")
@superadmin_required
def cronjob_alias():
    return redirect(url_for("scheduler_admin.dashboard"))


@scheduler_admin.get("/admin/pianificazioni/api")
@superadmin_required
def api_dashboard():
    return redacted_json_response(build_scheduler_admin_surface())
