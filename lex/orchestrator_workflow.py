"""Pipeline bounded-context pura dell'orchestratore Lex."""

from __future__ import annotations

from types import SimpleNamespace

from .contracts import answer_contract_for
from .exceptions import LexGuardError


def _guardrail_reply(request, workflow: str, evidence: dict, verdict) -> str:
    coverage_gaps = list((evidence or {}).get("coverage_gaps") or [])
    base_lines: list[str] = []
    if workflow in {"normativa", "giurisprudenza", "prassi", "research", "fonti"}:
        base_lines.append(
            "Non posso completare una risposta legale affidabile con i riferimenti oggi verificati."
        )
    else:
        base_lines.append(
            "La richiesta richiede una verifica aggiuntiva prima di produrre una risposta affidabile."
        )
    for warning in list(getattr(verdict, "warnings", []) or [])[:2]:
        base_lines.append(f"Avviso: {warning}")
    for gap in coverage_gaps[:2]:
        base_lines.append(f"Gap evidenza: {gap}")
    base_lines.append("Azione suggerita: integra fonti ufficiali o valida manualmente il passaggio critico.")
    return "\n".join(base_lines)


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
        contract = answer_contract_for(workflow)
        if not contract.allow_abstention:
            raise LexGuardError("; ".join(post.reasons or ["Response blocked by guards"]))
        draft = SimpleNamespace(
            text=_guardrail_reply(request, workflow, evidence, post),
            metadata={
                "provider": "guardrail",
                "status": "blocked",
                "guard_blocked": True,
                "reason": "; ".join(post.reasons or []),
            },
        )

    response = orchestrator.response_formatter.build_response(
        request=request,
        context=context,
        workflow=workflow,
        evidence=evidence,
        draft=draft,
        verdict=post,
    )

    if orchestrator.memory is not None:
        orchestrator.memory.persist(request, workflow, context, evidence, response)
    if orchestrator.telemetry is not None:
        orchestrator.telemetry.record(request, workflow, context, evidence, response)

    return response
