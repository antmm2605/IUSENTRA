"""Shell React per Portale Cliente studio e Mini App Cliente."""

from __future__ import annotations

from flask import Blueprint, current_app, make_response, request

from web.blueprints.react_shell import render_react_shell_response
from web.services.feature_flags import is_feature_enabled


client_portal_shell = Blueprint("client_portal_shell", __name__)
portale_cliente = Blueprint("portale_cliente", __name__)


def _feature_disabled_response():
    response = make_response("Portale Cliente non attivo per questo studio.", 403)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@client_portal_shell.get("/app/portale-clienti")
@client_portal_shell.get("/app/portale-clienti/")
@client_portal_shell.get("/app/portale-clienti/impostazioni")
@client_portal_shell.get("/app/portale-clienti/impostazioni/")
def studio_client_portal_shell():
    if not is_feature_enabled("routes.appV2.clientPortal.enabled", current_app.config):
        return _feature_disabled_response()
    return render_react_shell_response(request.path.lstrip("/"))


@portale_cliente.get("/portale-cliente")
@portale_cliente.get("/portale-cliente/")
@portale_cliente.get("/portale-cliente/<path:spa_path>")
def public_client_portal_shell(spa_path: str = ""):
    if not is_feature_enabled("routes.appV2.clientPortal.enabled", current_app.config):
        return _feature_disabled_response()
    return render_react_shell_response(request.path.lstrip("/"))
