"""Errori applicativi del modulo SIGP."""

from __future__ import annotations


class SigpError(RuntimeError):
    """Errore base del modulo SIGP."""


class SigpSchemaMissingError(SigpError):
    """Schema XSD ufficiale non ancora disponibile in locale."""
