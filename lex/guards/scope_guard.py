"""Perimetro operativo delle richieste Lex."""

from __future__ import annotations


class ScopeGuard:
    def normalize_message(self, message: str) -> str:
        return " ".join(str(message or "").split()).strip()

    def ensure_message(self, message: str) -> str:
        normalized = self.normalize_message(message)
        if not normalized:
            raise ValueError("Domanda mancante.")
        return normalized
