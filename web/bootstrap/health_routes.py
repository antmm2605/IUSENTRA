"""Health and runtime probe routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from flask import Flask, current_app, jsonify

from web.services.observability_runtime import build_observability_payload


def register_health_routes(
    app: Flask,
    *,
    get_clienti: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_agenda: Callable[[], object],
    get_scadenziario: Callable[[], object],
) -> None:
    """Register monitoring endpoints that must stay lightweight."""

    @app.route("/api/health")
    def api_health():
        stato = {"ok": True, "timestamp": datetime.now().isoformat(), "moduli": {}}
        try:
            gc = get_clienti()
            stato["moduli"]["clienti"] = {"ok": True, "totale": gc.statistiche()["totale"]}
        except Exception as e:
            stato["moduli"]["clienti"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            gf = get_fascicoli()
            stato["moduli"]["fascicoli"] = {"ok": True, "attivi": gf.statistiche()["attivi"]}
        except Exception as e:
            stato["moduli"]["fascicoli"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            ga = get_agenda()
            stato["moduli"]["agenda"] = {"ok": True, "totale": ga.statistiche()["totale"]}
        except Exception as e:
            stato["moduli"]["agenda"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        try:
            gs = get_scadenziario()
            stato["moduli"]["scadenziario"] = {"ok": True, "aperte": gs.statistiche()["aperte"]}
        except Exception as e:
            stato["moduli"]["scadenziario"] = {"ok": False, "errore": str(e)}
            stato["ok"] = False
        codice = 200 if stato["ok"] else 503
        return jsonify(stato), codice

    @app.route("/api/metriche/runtime")
    def api_runtime_metrics():
        try:
            payload = build_observability_payload(current_app._get_current_object())
            return jsonify(payload), 200
        except Exception as exc:
            current_app.logger.exception("Errore api_runtime_metrics: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200
