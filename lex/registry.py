"""Registry centrale del bounded context Lex."""

from __future__ import annotations

from .adapters import LexAdapterRegistry
from .context.builder import LexContextBuilder
from .guards.orchestrator import GuardOrchestrator
from .insights import LexInsightsService
from .memory.service import LexMemoryService
from .orchestrator import LexOrchestrator
from .providers.registry import ProviderRegistry
from .research import LexResearchService
from .retrieval.context_builder import RetrievalContextBuilder
from .retrieval.orchestrator import RetrievalOrchestrator
from .router import LexRouter
from .service import LexService
from .telemetry.logging import LexTelemetry


def build_lex_service() -> LexService:
    research_service = LexResearchService()
    adapter_registry = LexAdapterRegistry()
    insights_service = LexInsightsService()
    return LexService(
        orchestrator=LexOrchestrator(
            router=LexRouter(),
            workflow_context_builder=LexContextBuilder(),
            retrieval_orchestrator=RetrievalOrchestrator(
                research_service=research_service,
                context_builder=RetrievalContextBuilder(),
            ),
            guard_orchestrator=GuardOrchestrator(),
            provider_registry=ProviderRegistry(),
            telemetry=LexTelemetry(),
            memory=LexMemoryService(
                adapter_registry=adapter_registry,
                insights_service=insights_service,
            ),
        )
    )