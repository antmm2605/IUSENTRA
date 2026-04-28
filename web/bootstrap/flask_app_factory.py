"""Factory base Flask per i profili web e scheduler."""

from __future__ import annotations

import os
from typing import Any

from flask import Flask

from core.config import load_hardening_config
from core.security.rate_limit import register_rate_limiter
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
    hardening = load_hardening_config({**cfg, "TESTING": app.config["TESTING"]})
    app.config.update(
        DATABASE_URL=hardening.database_url,
        REDIS_URL=hardening.redis_url,
        CACHE_TTL_SECONDS=hardening.cache_ttl_seconds,
        SESSION_REDIS_ENABLED=hardening.session_redis_enabled,
        MAX_UPLOAD_MB=hardening.max_upload_mb,
        ALLOWED_UPLOAD_EXTENSIONS=",".join(hardening.allowed_upload_extensions),
        ALLOWED_UPLOAD_MIME_TYPES=",".join(hardening.allowed_upload_mime_types),
        RATELIMIT_ENABLED=hardening.ratelimit_enabled,
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", hardening.redis_url or "memory://"),
        RATELIMIT_DEFAULT=hardening.ratelimit_default,
        SECURITY_HEADERS_ENABLED=hardening.security_headers_enabled,
        CSP_REPORT_ONLY=hardening.csp_report_only,
        PROMETHEUS_ENABLED=hardening.prometheus_enabled,
        BACKUP_DIR=str(hardening.backup_dir),
        BACKUP_RETENTION_DAYS=hardening.backup_retention_days,
        BACKUP_ENCRYPTION_ENABLED=hardening.backup_encryption_enabled,
    )
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
    register_rate_limiter(app)
    if app.config.get("SECRET_KEY_EPHEMERAL"):
        app.logger.warning(
            "PCT_SECRET_KEY non configurata o insicura: uso una chiave effimera valida solo per questo avvio."
        )
    return app, cfg
