"""Endpoint opzionali del motore giornaliero Legal Intelligence.

Il blueprint principale dell'app resta in web.blueprints.legal_intelligence.
Questo modulo espone funzioni riusabili per eventuali mount dedicati.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from .engine import LegalIntelligenceDailyEngine


daily_blueprint = Blueprint("legal_intelligence_daily_engine", __name__)


def engine_from_app() -> LegalIntelligenceDailyEngine:
    db_path = current_app.config.get("LEGAL_INTELLIGENCE_DAILY_DB", "./data/legal_intelligence/daily.sqlite")
    return LegalIntelligenceDailyEngine(db_path)


@daily_blueprint.get("/daily/snapshot")
def daily_snapshot():
    return jsonify({"ok": True, "snapshot": engine_from_app().dashboard_snapshot()})
