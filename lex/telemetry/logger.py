"""Logging minimale per Lex."""

from __future__ import annotations

from flask import current_app


def log_exception(message: str, *args) -> None:
    current_app.logger.exception(message, *args)
