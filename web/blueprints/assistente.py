"""Facciata compatibile del blueprint Lex.

Il motore e il wiring reale vivono nel package ``lex/``.
Questo modulo mantiene solo il nome storico del blueprint.
"""

from __future__ import annotations

from lex.blueprint import create_lex_blueprint
from lex.runtime_dependencies import (
    build_runtime_lex_dependencies,
    require_authenticated_flask_user,
)

_build_lex_dependencies = build_runtime_lex_dependencies
_richiedi_login = require_authenticated_flask_user


assistente = create_lex_blueprint(
    dependency_factory=_build_lex_dependencies,
    login_required=_richiedi_login,
)


__all__ = [
    "assistente",
    "_build_lex_dependencies",
    "_richiedi_login",
]
