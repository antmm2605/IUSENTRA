"""Pipeline bounded-context pura dell'orchestratore Lex."""

from __future__ import annotations

from .exceptions import LexGuardError


def run_workflow(orchestrator, request):
    if (
        orchestrator.workflow_router is None
        or orchestrator.retrieval_orchestrator is None
        or orchestrator.guard_orchestrator is None
        or orchestrator.provider_registry is None
    ):
        raise RuntimeError("LexOrchestrator.run richiede i componenti applicativi del bounded context.")

    workflow = orchestrator.workflow_router.resolve_workflow(request)
    context = orchestrator.workflow_context_builder.build_request_context(request, workflow)

    pre = orchestrator.guard_orchestrator.run_pre(request, context, workflow)
    if not pre.allowed:
        raise LexGuardError("; ".join(pre.reasons or ["Request blocked by guards"]))

    evidence = orchestrator.retrieval_orchestrator.collect(request, context, workflow)
    provider = orchestrator.provider_registry.pick(request, context, workflow, evidence)
    draft = provider.generate(request=request, context=context, evidence=evidence, workflow=workflow)

    post = orchestrator.guard_orchestrator.run_post(request, context, workflow, evidence, draft)
    if not post.allowed:
        raise LexGuardError("; ".join(post.reasons or ["Response blocked by guards"]))

    response = orchestrator.response_formatter.build_response(
        request=request,
        context=context,
        workflow=workflow,
        evidence=evidence,
        draft=draft,
        verdict=post,
    )

    if orchestrator.telemetry is not None:
        orchestrator.telemetry.record(request, workflow, context, evidence, response)
    if orchestrator.memory is not None:
        orchestrator.memory.persist(request, workflow, context, response)

    return response
