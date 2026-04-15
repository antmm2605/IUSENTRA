"""Contesto runtime AI e feature operative per Lex."""

from __future__ import annotations

from flask import has_app_context

from lex.providers.health import resolved_runtime


def build_runtime_context(request) -> dict[str, str]:
    if not has_app_context():
        return {"provider": "ollama", "source": "no_app_context"}
    return dict(resolved_runtime())
