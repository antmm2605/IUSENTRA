"""Eccezioni applicative del modulo Lex."""

from __future__ import annotations


class LexError(Exception):
    """Eccezione base del bounded context Lex."""


class LexValidationError(LexError):
    """Payload o input non valido."""


class LexPermissionError(LexError):
    """Richiesta bloccata per permessi insufficienti."""


class LexGuardError(LexError):
    """Richiesta o risposta bloccata dai guard rail."""


class LexProviderError(LexError):
    """Errore del provider AI sottostante."""


class LexRetrievalError(LexError):
    """Errore di retrieval o accesso alle fonti."""
