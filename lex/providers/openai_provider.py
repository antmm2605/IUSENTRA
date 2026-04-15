"""Segnaposto per futuri provider hosted di Lex."""

from __future__ import annotations


class OpenAIProvider:
    def generate(self, *args, **kwargs):
        raise NotImplementedError("Provider hosted non ancora attivo nel modulo Lex.")
