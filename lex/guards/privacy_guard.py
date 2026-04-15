"""Filtri minimi privacy per i payload Lex."""

from __future__ import annotations

from typing import Any


class PrivacyGuard:
    def sanitize_sections(self, sections: dict[str, Any] | None) -> dict[str, Any]:
        return dict(sections or {})

    def check(self, **kwargs):
        from lex.contracts import GuardVerdict

        return GuardVerdict(allowed=True)
