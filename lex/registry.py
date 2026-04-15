"""Registry centrale del bounded context Lex."""

from __future__ import annotations

from .context.builder import LexContextBuilder
from .guards.orchestrator import GuardOrchestrator
from .memory.service import LexMemoryService
from .orchestrator import LexOrchestrator
from .providers.registry import ProviderRegistry
from .retrieval.orchestrator import RetrievalOrchestrator
from .router import LexRouter
from .service import LexService
from .telemetry.logging import LexTelemetry


def build_lex_service() -> LexService:
    return LexService(
        orchestrator=LexOrchestrator(
            router=LexRouter(),
            workflow_context_builder=LexContextBuilder(),
            retrieval_orchestrator=RetrievalOrchestrator(),
            guard_orchestrator=GuardOrchestrator(),
            provider_registry=ProviderRegistry(),
            telemetry=LexTelemetry(),
            memory=LexMemoryService(),
        )
    )
