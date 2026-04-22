from __future__ import annotations

from functools import wraps

from flask import Blueprint, render_template, request

from web.services.studio_site_runtime import build_platform_sites_payload, superadmin_identity_or_403


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
    payload = build_platform_sites_payload(query=str(request.args.get("q") or "").strip())
    return render_template("admin/studio_site_console.html", payload=payload)
