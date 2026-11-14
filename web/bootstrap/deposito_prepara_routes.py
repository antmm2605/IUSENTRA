"""Legacy deposito preparation route registration."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask

from web.blueprints.react_shell import render_react_shell_response


def register_deposito_prepara_route(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_config_studio: Callable[[], object],
    deposito_correction_context: Callable[[object], dict[str, Any]],
    luogo_timbro_firma_visibile: Callable[[], str],
) -> None:
    """Register React-first deposito preparation page and legacy fallback."""

    @app.route("/fascicoli/<id_fasc>/deposito/prepara", methods=["GET"])
    def deposito_prepara(id_fasc):
        """Mostra il riepilogo documenti e la guida al deposito telematico."""
        return render_react_shell_response(f"fascicoli/{id_fasc}/deposito/prepara")
