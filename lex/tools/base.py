"""Contratto base dei tool Lex."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLexTool(ABC):
    tool_name = "base"

    @abstractmethod
    def run(self, **kwargs):
        raise NotImplementedError
