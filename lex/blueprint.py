"""Factory blueprint del modulo Lex."""

from __future__ import annotations

from flask import Blueprint

from .dependencies import DependencyFactory
from .routes import register_routes
from .runtime_dependencies import (
    build_runtime_lex_dependencies,
    require_authenticated_flask_user,
)
from .service import LexService


def create_lex_blueprint(
    *,
    dependency_factory: DependencyFactory,
    login_required=None,
) -> Blueprint:
    bp = Blueprint("assistente", __name__)
    service = LexService(dependency_factory=dependency_factory)
    register_routes(bp, service=service, login_required=login_required)
    return bp


def build_runtime_lex_blueprint() -> Blueprint:
    return create_lex_blueprint(
        dependency_factory=build_runtime_lex_dependencies,
        login_required=require_authenticated_flask_user,
    )
