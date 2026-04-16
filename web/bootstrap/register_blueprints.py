"""Centralized blueprint registration for the web application."""

from __future__ import annotations

from flask import Flask

from web.bootstrap.blueprint_registry import BLUEPRINT_REGISTRY


def register_blueprints(app: Flask) -> None:
    """Register all modular blueprints on the Flask app."""

    for entry in BLUEPRINT_REGISTRY:
        if not entry.is_enabled(app.config):
            continue
        app.register_blueprint(entry.load_blueprint())
