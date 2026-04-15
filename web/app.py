"""
Flask web application - Studio Legale PCT.

Avvio:
    python -m web
    oppure: flask --app web.app run --debug
"""

from __future__ import annotations

from flask import Flask

from lex.providers.local_ai_service import get_local_ai_service
from pct import __version__ as APP_VERSION
from web.bootstrap.app_wiring import register_app_wiring
from web.bootstrap.flask_app_factory import create_flask_app
from web.bootstrap.runtime_bundle import build_application_runtime_bundle


def create_app(config: dict | None = None) -> Flask:
    """Crea l'app Flask e delega bootstrap, runtime e wiring ai moduli dedicati."""

    app, cfg = create_flask_app(config)
    runtime_bundle = build_application_runtime_bundle(app, cfg)
    if runtime_bundle.scheduler_only:
        return app

    register_app_wiring(
        app,
        app_version=APP_VERSION,
        core=runtime_bundle.core,
        fascicoli=runtime_bundle.fascicoli,
        telematico=runtime_bundle.telematico,
        pdp_penale=runtime_bundle.pdp_penale,
        ocr_runtime=runtime_bundle.ocr_runtime,
        get_local_ai_service=get_local_ai_service,
    )
    return app
