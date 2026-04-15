"""Value object del dominio Lex."""

from __future__ import annotations


class ConfidenceScore:
    def __init__(self, value: float):
        self.value = value
