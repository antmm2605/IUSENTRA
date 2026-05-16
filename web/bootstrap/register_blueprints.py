"""Centralized blueprint registration for the web application."""

from __future__ import annotations

from flask import Flask

from web.bootstrap.blueprint_registry import BLUEPRINT_REGISTRY


def register_blueprints(app: Flask) -> None:
    """Register all modular blueprints on the Flask app.

    Le voci del registry possono richiedere un nome di registrazione e un
    url_prefix esplicito (per montare lo stesso Blueprint su piu' prefissi,
    es. alias canonici come `/ricerca-legale` per `/legal-intelligence`).
    """

    for entry in BLUEPRINT_REGISTRY:
        if not entry.is_enabled(app.config):
            continue
        blueprint = entry.load_blueprint()
        kwargs: dict[str, object] = {}
        if entry.name != blueprint.name:
            kwargs["name"] = entry.name
        if entry.url_prefix:
            kwargs["url_prefix"] = entry.url_prefix
        app.register_blueprint(blueprint, **kwargs)
