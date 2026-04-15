"""Service layer del modulo Lex."""

from __future__ import annotations

from typing import Any

from .dependencies import DependencyFactory, LexDependencies
from .orchestrator import LexOrchestrator


class LexService:
    def __init__(self, *, dependency_factory: DependencyFactory) -> None:
        self._dependency_factory = dependency_factory

    def _orchestrator(self) -> LexOrchestrator:
        dependencies: LexDependencies = self._dependency_factory()
        return LexOrchestrator(dependencies)

    def stato(self) -> tuple[dict[str, Any], int]:
        return self._orchestrator().status_payload()

    def context(self, *, user, studio, data: dict[str, Any]) -> tuple[dict[str, Any], int]:
        return self._orchestrator().build_context_response(user=user, studio=studio, data=data)

    def warmup(self, *, question: str, context_label: str) -> tuple[dict[str, Any], int]:
        return self._orchestrator().warmup_response(question=question, context_label=context_label)

    def attachments(self, *, files: list[dict[str, Any]]) -> tuple[dict[str, Any], int]:
        return self._orchestrator().attachments_response(files=files)

    def documento(self, *, data: dict[str, Any]):
        return self._orchestrator().document_response(data=data)

    def chat(self, *, user, studio, data: dict[str, Any]):
        return self._orchestrator().chat_response(user=user, studio=studio, data=data)
