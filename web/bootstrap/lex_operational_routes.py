"""Route operative di Lex oltre il widget di chat."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, jsonify, request

from web.services.lex_operational_surface import build_lex_operational_payload
from web.blueprints.react_shell import render_react_shell_response


def register_lex_operational_routes(
    app: Flask,
    *,
    get_workspace_intelligente: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_telematico: Callable[[], object],
) -> None:
    """Registra le superfici operative di Lex e la loro API JSON."""

    @app.route("/lex-operativo")
    def lex_operativo():
        # Lex operativo: pagina React (LexOperativoPage).
        return render_react_shell_response("lex-operativo")

    @app.route("/api/lex-operativo")
    def api_lex_operativo():
        try:
            horizon_days = max(int(request.args.get("giorni", 14) or 14), 1)
            payload = build_lex_operational_payload(
                get_workspace_intelligente=get_workspace_intelligente,
                get_fascicoli=get_fascicoli,
                get_telematico=get_telematico,
                horizon_days=horizon_days,
            )
            return jsonify({"ok": True, **payload})
        except Exception as exc:
            app.logger.exception("Errore api_lex_operativo: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

