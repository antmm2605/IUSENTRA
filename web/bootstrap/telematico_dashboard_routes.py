"""Telematico dashboard routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, jsonify
from web.blueprints.react_shell import render_react_shell_response


def register_telematico_dashboard_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    get_telematico: Callable[[], object],
    _backfill_telematico_from_existing_fascicoli: Callable[[], dict[str, int]],
    _build_access_status_payload: Callable[[str], dict],
    _telematico_dashboard_warning_message: Callable[[Exception], str],
) -> None:
    """Register telematico dashboard and connection status routes."""

    @app.route("/api/telematico/connection-status", methods=["GET"])
    def api_telematico_connection_status():
        try:
            portal_labels = {
                "pst": "PST / PolisWeb",
                "pdp": "PDP Penale",
                "pat": "PAT / SIGA",
                "ptt": "PTT / SIGIT",
            }
            cards = []
            for portale in ("pst", "pdp", "pat", "ptt"):
                payload = _build_access_status_payload(portale)
                spec = dict(payload.get("spec") or {})
                cards.append(
                    {
                        "portale": portale,
                        "label": portal_labels[portale],
                        "color": spec.get("color"),
                        "status_text": payload.get("status_text"),
                        "environment_label": payload.get("environment_label"),
                        "demo_mode": bool(payload.get("demo_mode")),
                        "pkcs11_mode": bool(payload.get("pkcs11_mode")),
                        "browser_channel_required": bool(payload.get("browser_channel_required")),
                        "last_sync_at": payload.get("last_sync_at"),
                    }
                )
            return jsonify({"ok": True, "cards": cards})
        except Exception as e:
            app.logger.exception("Errore api_telematico_connection_status: %s", e)
            return jsonify({"ok": False, "errore": str(e), "cards": []}), 200

    @app.route("/telematico", methods=["GET"])
    def telematico_dashboard():
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("telematico")
