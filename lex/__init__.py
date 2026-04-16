"""Modulo Lex: bounded context AI del gestionale IUSENTRA."""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "LexOrchestrator": ("lex.orchestrator", "LexOrchestrator"),
    "LexService": ("lex.service", "LexService"),
    "build_lex_service": ("lex.registry", "build_lex_service"),
    "build_runtime_lex_dependencies": ("lex.runtime_dependencies", "build_runtime_lex_dependencies"),
    "create_lex_blueprint": ("lex.blueprint", "create_lex_blueprint"),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'lex' has no attribute {name!r}")
    module_name, attribute_name = target
    module = import_module(module_name)
    return getattr(module, attribute_name)

