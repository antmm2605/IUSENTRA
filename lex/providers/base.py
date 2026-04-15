"""Contratto base dei provider AI di Lex."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseProvider(ABC):
    provider_name = "base"

    @abstractmethod
    def generate(self, request, context, evidence, workflow):
        raise NotImplementedError
