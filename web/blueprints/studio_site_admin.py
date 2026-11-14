from __future__ import annotations

from functools import wraps

from flask import Blueprint

from web.services.piattaforma_shell_runtime import render_piattaforma_shell
from web.services.studio_site_runtime import superadmin_identity_or_403


studio_site_admin = Blueprint("studio_site_admin", __name__, url_prefix="/admin/siti-studio")


def superadmin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        superadmin_identity_or_403()
        return fn(*args, **kwargs)

    return wrapper


@studio_site_admin.get("/")
@superadmin_required
def console():
    return render_piattaforma_shell("siti-studio", "Siti degli studi")
