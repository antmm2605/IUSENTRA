"""Controlli di accesso per Lex."""

from __future__ import annotations


class AuthorizationGuard:
    """Guardia minima: Lex lavora solo in sessione autenticata."""

    def ensure_authenticated(self, user) -> None:
        if user is None:
            raise PermissionError("Utente non autenticato.")

    def ensure_can_access(self, *, user, studio, pratica_id: str = "") -> None:
        self.ensure_authenticated(user)
