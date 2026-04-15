"""Orchestratore del flusso Lex."""

from __future__ import annotations

from .context import LexContextBuilder
from .dependencies import LexDependencies
from .formatting.answer_builder import AnswerBuilder
from .guards import AuthorizationGuard, GroundingGuard, OutputGuard, ScopeGuard
from .memory.conversation_state import (
    messages_with_effective_question,
    resolve_current_and_previous_user_messages,
)
from .orchestrator_http import (
    attachments_response,
    build_context_response,
    build_context_payload,
    chat_response,
    clean_spaces,
    document_response,
    followup_prompt_block,
    routing_prompt_block,
    status_payload,
    warmup_response,
)
from .orchestrator_workflow import run_workflow
from .providers.local_llm import LocalLLMProvider
from .retrieval import LexSearchRanker


class LexOrchestrator:
    def __init__(
        self,
        dependencies: LexDependencies | None = None,
        *,
        router=None,
        workflow_context_builder=None,
        retrieval_orchestrator=None,
        guard_orchestrator=None,
        provider_registry=None,
        formatter=None,
        telemetry=None,
        memory=None,
    ) -> None:
        self.dependencies = dependencies
        self.auth_guard = AuthorizationGuard()
        self.scope_guard = ScopeGuard()
        self.context_builder = LexContextBuilder()
        self.search_ranker = LexSearchRanker()
        self.grounding_guard = GroundingGuard()
        self.output_guard = OutputGuard()
        self.answer_builder = AnswerBuilder()
        self.llm_provider = LocalLLMProvider()
        self.workflow_router = router
        self.workflow_context_builder = workflow_context_builder or self.context_builder
        self.retrieval_orchestrator = retrieval_orchestrator
        self.guard_orchestrator = guard_orchestrator
        self.provider_registry = provider_registry
        self.response_formatter = formatter or self.answer_builder
        self.telemetry = telemetry
        self.memory = memory

    def run(self, request):
        return run_workflow(self, request)

    def _build_context_payload(self, **kwargs):
        return build_context_payload(self, **kwargs)

    def _followup_prompt_block(self, followup) -> str:
        return followup_prompt_block(followup)

    def _routing_prompt_block(self, routing, *, opening_line: str = "") -> str:
        return routing_prompt_block(routing, opening_line=opening_line)

    def status_payload(self):
        return status_payload(self)

    def build_context_response(self, *, user, studio, data):
        return build_context_response(
            self,
            user=user,
            studio=studio,
            data=data,
            resolve_messages=resolve_current_and_previous_user_messages,
        )

    def warmup_response(self, *, question: str, context_label: str):
        return warmup_response(self, question=question, context_label=context_label)

    def attachments_response(self, *, files):
        return attachments_response(self, files=files)

    def document_response(self, *, data):
        return document_response(self, data=data)

    def chat_response(self, *, user, studio, data):
        return chat_response(
            self,
            user=user,
            studio=studio,
            data=data,
            resolve_messages=resolve_current_and_previous_user_messages,
            messages_with_effective_question=messages_with_effective_question,
        )


__all__ = [
    "LexOrchestrator",
    "clean_spaces",
    "messages_with_effective_question",
    "resolve_current_and_previous_user_messages",
]
