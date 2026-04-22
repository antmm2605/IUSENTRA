"""Factory base Flask per i profili web e scheduler."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask

from web.services.observability_runtime import register_observability_runtime
from web.services.security_runtime import apply_security_defaults
from web.services.structured_logging import configure_structured_logging
from web.extensions import sock


def create_flask_app(config: dict[str, Any] | None = None) -> tuple[Flask, dict[str, Any]]:
    """Crea la Flask app base e applica i default di sicurezza/runtime comuni."""

    cfg = dict(config or {})
    app = Flask("web", template_folder="templates", static_folder="static")
    app.config["TESTING"] = bool(cfg.get("TESTING", False))
    app.config["PCT_SCHEDULER_WORKER"] = bool(cfg.get("SCHEDULER_ONLY"))
    configure_structured_logging(app, cfg)
    sock.init_app(app)

    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    apply_security_defaults(
        app,
        {
            **cfg,
            "PCT_SECRET_KEY": os.getenv("PCT_SECRET_KEY", ""),
            "PCT_HTTPS": cfg.get("PCT_HTTPS", os.getenv("PCT_HTTPS", "")),
        },
    )
    register_observability_runtime(app)
    if app.config.get("SECRET_KEY_EPHEMERAL"):
        app.logger.warning(
            "PCT_SECRET_KEY non configurata o insicura: uso una chiave effimera valida solo per questo avvio."
        )
    return app, cfg
