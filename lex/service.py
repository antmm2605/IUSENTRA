"""Service layer del modulo Lex."""

from __future__ import annotations

from typing import Any

from .contracts import LexRequest as WorkflowLexRequest
from .dependencies import DependencyFactory, LexDependencies
from .orchestrator import LexOrchestrator


class LexService:
    def __init__(
        self,
        *,
        dependency_factory: DependencyFactory | None = None,
        orchestrator: LexOrchestrator | None = None,
    ) -> None:
        self._dependency_factory = dependency_factory
        self._application_orchestrator = orchestrator

    def _orchestrator(self) -> LexOrchestrator:
        if self._dependency_factory is None:
            raise RuntimeError("dependency_factory non configurata per le route HTTP di Lex.")
        dependencies: LexDependencies = self._dependency_factory()
        return LexOrchestrator(dependencies)

    def _workflow_orchestrator(self) -> LexOrchestrator:
        if self._application_orchestrator is None:
            raise RuntimeError("orchestrator applicativo non configurato per il bounded context Lex.")
        return self._application_orchestrator

    def ask(self, request: WorkflowLexRequest):
        return self._workflow_orchestrator().run(request)

    def summarize_fascicolo(self, request: WorkflowLexRequest):
        request.intent = "summarize_fascicolo"
        return self.ask(request)

    def prepare_udienza(self, request: WorkflowLexRequest):
        request.intent = "prepare_udienza"
        return self.ask(request)

    def explain_telematico_error(self, request: WorkflowLexRequest):
        request.intent = "explain_telematico_error"
        return self.ask(request)

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
