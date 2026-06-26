"""Health and runtime probe routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import os
from zoneinfo import ZoneInfo

from flask import Flask, current_app, jsonify
from pct import __version__ as APP_VERSION

from core.health import dependencies_payload, live_payload, ready_payload
from core.metrics import prometheus_payload
from web.services.observability_runtime import build_observability_payload

ROME_TZ = ZoneInfo("Europe/Rome")


def _now_rome_iso() -> str:
    return datetime.now(ROME_TZ).isoformat(timespec="seconds")


def _runtime_storage_root() -> str:
    configured = current_app.config.get("PCT_DATA_ROOT") or os.getenv("PCT_DATA_ROOT")
    if configured:
        return str(configured)
    return "/data" if os.path.isdir("/data") else "data"


def register_health_routes(
    app: Flask,
    *,
    get_clienti: Callable[[], object],
    get_fascicoli: Callable[[], object],
    get_agenda: Callable[[], object],
    get_scadenziario: Callable[[], object],
) -> None:
    """Register monitoring endpoints that must stay lightweight."""

    @app.route("/api/pronto")
    def api_ready():
        return (
            jsonify(
                {
                    "ok": True,
                    "stato": "pronto",
                    "versione": APP_VERSION,
                    "timestamp": _now_rome_iso(),
                    "timezone": "Europe/Rome",
                }
            ),
            200,
        )

    @app.route("/api/health")
    def api_health():
        stato = {"ok": True, "timestamp": _now_rome_iso(), "timezone": "Europe/Rome", "moduli": {}}
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

    @app.route("/health/live")
    def health_live():
        payload, status_code = live_payload(APP_VERSION)
        return jsonify(payload), status_code

    @app.route("/health/ready")
    def health_ready():
        payload, status_code = ready_payload(
            version=APP_VERSION,
            database_url=str(current_app.config.get("DATABASE_URL") or ""),
            redis_url=str(current_app.config.get("REDIS_URL") or ""),
            storage_root=_runtime_storage_root(),
        )
        return jsonify(payload), status_code

    @app.route("/health/dependencies")
    def health_dependencies():
        payload, status_code = dependencies_payload(
            version=APP_VERSION,
            database_url=str(current_app.config.get("DATABASE_URL") or ""),
            redis_url=str(current_app.config.get("REDIS_URL") or ""),
            ollama_url=str(current_app.config.get("OLLAMA_BASE_URL") or current_app.config.get("PCT_LOCAL_AI_BASE_URL") or ""),
            smtp_configured=bool(current_app.config.get("PCT_SMTP_HOST") or current_app.config.get("SMTP_HOST")),
        )
        return jsonify(payload), status_code

    @app.route("/metrics")
    def prometheus_metrics():
        if not current_app.config.get("PROMETHEUS_ENABLED", True):
            return "Metriche disabilitate\n", 404, {"Content-Type": "text/plain; charset=utf-8"}
        payload = build_observability_payload(current_app._get_current_object())
        return prometheus_payload(payload), 200, {"Content-Type": "text/plain; version=0.0.4; charset=utf-8"}
