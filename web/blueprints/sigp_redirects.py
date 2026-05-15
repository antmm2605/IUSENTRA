"""Redirect dei vecchi ingressi SIGP verso il wizard PST unico."""

from __future__ import annotations

from flask import Blueprint, redirect, url_for

sigp_redirects = Blueprint("sigp_redirects", __name__)


@sigp_redirects.route("/sigp", defaults={"_unused": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@sigp_redirects.route("/sigp/", defaults={"_unused": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@sigp_redirects.route("/sigp/<path:_unused>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def redirect_sigp_to_pst_acquisition(_unused: str = ""):
    return redirect(url_for("portale_acquisizione_wizard", portale="pst"), code=303)


@sigp_redirects.route("/sigp-sync", defaults={"_unused": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@sigp_redirects.route("/sigp-sync/", defaults={"_unused": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
@sigp_redirects.route("/sigp-sync/<path:_unused>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def redirect_sigp_sync_to_pst_acquisition(_unused: str = ""):
    return redirect(url_for("portale_acquisizione_wizard", portale="pst"), code=303)
