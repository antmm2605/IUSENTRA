"""Rotte React del blocco finale Studio / Amministrazione."""

from __future__ import annotations

from functools import wraps

from flask import Flask, abort, g, redirect, request, url_for

from web.blueprints.react_shell import render_react_shell_response


FINAL_REACT_ROUTES: dict[str, str] = {
    "/studio": "studio",
    "/compensi-forensi": "compensi-forensi",
    "/redazione-atti": "redazione-atti",
    "/ricerca-legale": "ricerca-legale",
    "/strumenti-operativi": "strumenti-operativi",
    "/notifiche-whatsapp": "notifiche-whatsapp",
    "/incassi-pagamenti": "incassi-pagamenti",
    "/impostazioni-studio": "impostazioni-studio",
    "/sincronizzazione-calendari": "sincronizzazione-calendari",
    "/amministrazione": "amministrazione",
    "/registro-attivita": "registro-attivita",
    "/database": "database",
    "/registro-gdpr": "registro-gdpr",
}

FINAL_REACT_PERMISSIONS: dict[str, str] = {
    "/amministrazione": "utenti.leggi",
    "/registro-attivita": "audit.leggi",
    "/database": "utenti.leggi",
    "/registro-gdpr": "utenti.leggi",
}


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login", next=request.full_path.rstrip("?")))
        return fn(*args, **kwargs)

    return wrapper


def register_react_final_block_routes(app: Flask) -> None:
    """Registra gli alias ufficiali del blocco finale migrato a React."""

    for route, spa_path in FINAL_REACT_ROUTES.items():

        def view(route: str = route, spa_path: str = spa_path):
            required_permission = FINAL_REACT_PERMISSIONS.get(route)
            user = g.get("utente_corrente")
            if required_permission and (not user or not user.ha_permesso(required_permission)):
                abort(403)
            return render_react_shell_response(spa_path)

        endpoint = f"react_final_{spa_path.replace('/', '_').replace('-', '_')}"
        app.add_url_rule(route, endpoint, _richiedi_login(view), methods=["GET"])
