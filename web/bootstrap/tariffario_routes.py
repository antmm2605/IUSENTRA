"""Tariffario routes extracted from web.app."""

from __future__ import annotations

from flask import Flask, redirect, request, url_for

from web.blueprints.react_shell import render_react_shell_response


def register_tariffario_routes(app: Flask) -> None:
    """Register tariffario route and keep its runtime isolated from web.app."""

    @app.route("/tariffario", methods=["GET", "POST"])
    def tariffario():
        # Tariffario: pagina React (TariffarioPage); il calcolo passa da /api/v1/ui/tariffario/calcola.
        if request.method == "POST":
            return redirect(url_for("tariffario"))
        return render_react_shell_response("tariffario")
