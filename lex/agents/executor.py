"""Esecutore governato dei piani agentici."""

from __future__ import annotations

from typing import Any, Iterable

from lex.tools.registry import LexToolRegistry

from .audit import record_agent_audit
from .metrics import calculate_run_metric
from .models import AgentApproval, AgentProposal, AgentRun, AgentStep, utc_now_iso
from .policies import WorkflowAgentPolicyError, assert_step_executable
from .serialization import redact_value
from .synthesis import build_run_result


def _registry_block_payload(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict) or result.get("allowed") is not False:
        return None
    return {
        "blocked": True,
        "code": str(result.get("reason") or "strumento_bloccato"),
        "message": "Strumento Lex bloccato dalle policy o dai permessi.",
        "missing_permissions": list(result.get("missing_permissions") or []),
    }


class WorkflowAgentExecutor:
    def __init__(self, tool_registry: LexToolRegistry | None = None):
        self.tool_registry = tool_registry or LexToolRegistry()

    def _proposal_from_step(self, run: AgentRun, step: AgentStep) -> AgentProposal:
        proposal = AgentProposal(
            run_id=run.id,
            step_id=step.id,
            tool_name=step.tool_name,
            action_type=step.tool_name,
            title=step.title,
            impact=str(step.input_json.get("impatto") or step.input_json.get("descrizione") or step.title),
            risk_level=step.risk_level,
            payload=redact_value(step.input_json),
            editable_fields=tuple(step.input_json.get("editable_fields") or ("title", "titolo", "descrizione", "note", "data_scadenza", "minuti", "importo")),
        )
        step.status = "needs_approval"
        step.proposal_id = proposal.id
        return proposal

    def preview(
        self,
        run: AgentRun,
        *,
        tenant_scope: str,
        user_permissions: Iterable[str] | None = None,
    ) -> AgentRun:
        run.status = "running"
        run.started_at = utc_now_iso()
        evidence: dict[str, Any] = {}
        proposals: list[AgentProposal] = []
        for step in run.plan.steps:
            if step.mutates_state:
                proposals.append(self._proposal_from_step(run, step))
                continue
            try:
                assert_step_executable(
                    step,
                    tenant_scope=tenant_scope,
                    allow_writes=False,
                    write_feature_enabled=False,
                    approved=False,
                    user_permissions=user_permissions,
                )
                step.status = "running"
                result = self.tool_registry.run_tool(
                    step.tool_name,
                    allow_writes=False,
                    user_permissions=user_permissions,
                    **step.input_json,
                )
                blocked = _registry_block_payload(result)
                if blocked is not None:
                    step.status = "blocked"
                    step.error_message = blocked["message"]
                    evidence[step.step_key] = blocked
                    continue
                step.output_json = redact_value(result) if isinstance(result, dict) else {"result": redact_value(result)}
                step.status = "done"
                evidence[step.step_key] = step.output_json
            except WorkflowAgentPolicyError as exc:
                step.status = "blocked"
                step.error_message = exc.public_message
                evidence[step.step_key] = {"blocked": True, "code": exc.code, "message": exc.public_message}
            except Exception:
                step.status = "failed"
                step.error_message = "Errore controllato durante la lettura operativa."
                evidence[step.step_key] = {"failed": True, "message": step.error_message}
        run.evidence_json = evidence
        run.proposals = proposals
        run.status = "needs_approval" if proposals else "executed"
        run.completed_at = utc_now_iso() if not proposals else ""
        run.result_json = build_run_result(run)
        run.metrics = calculate_run_metric(run)
        run.audit_hash = record_agent_audit("workflow.preview", actor=run.created_by, run_id=run.id, details=run.to_dict())
        return run

    def execute_approved(
        self,
        run: AgentRun,
        approval: AgentApproval,
        *,
        tenant_scope: str,
        write_feature_enabled: bool,
        user_permissions: Iterable[str] | None = None,
    ) -> AgentRun:
        approved_ids = set(approval.approved_step_ids or [])
        if not approved_ids:
            raise WorkflowAgentPolicyError("approval_required", "Seleziona almeno una proposta da approvare.")
        proposal_by_step = {proposal.step_id: proposal for proposal in run.proposals}
        accepted = 0
        for step in run.plan.steps:
            if not step.mutates_state or step.id not in approved_ids:
                continue
            proposal = proposal_by_step.get(step.id)
            if proposal is None or proposal.status == "rejected":
                raise WorkflowAgentPolicyError("proposal_not_available", "Proposta non disponibile per l'approvazione.")
            changes = approval.modifications.get(step.id) or approval.modifications.get(proposal.id) or {}
            if changes:
                payload = dict(proposal.payload)
                for key in proposal.editable_fields:
                    if key in changes:
                        payload[key] = changes[key]
                proposal.payload = payload
                step.input_json.update(payload)
            assert_step_executable(
                step,
                tenant_scope=tenant_scope,
                allow_writes=True,
                write_feature_enabled=write_feature_enabled,
                approved=True,
                user_permissions=user_permissions,
            )
            result = self.tool_registry.run_tool(
                step.tool_name,
                allow_writes=True,
                user_permissions=user_permissions,
                **step.input_json,
            )
            if isinstance(result, dict) and result.get("allowed") is False:
                step.status = "blocked"
                step.error_message = str(result.get("reason") or "Scrittura bloccata.")
                proposal.status = "blocked"
                continue
            step.output_json = redact_value(result) if isinstance(result, dict) else {"result": redact_value(result)}
            step.status = "done"
            proposal.status = "executed"
            proposal.approved_by = approval.approved_by
            proposal.approved_at = utc_now_iso()
            accepted += 1
            record_agent_audit("workflow.write.executed", actor=approval.approved_by, run_id=run.id, details={"step": step.to_dict(), "result": step.output_json})
        rejected = sum(1 for proposal in run.proposals if proposal.status == "rejected")
        run.status = "executed" if accepted else "needs_approval"
        run.completed_at = utc_now_iso() if accepted else run.completed_at
        run.result_json = build_run_result(run)
        run.metrics = calculate_run_metric(run, accepted_actions=accepted, rejected_actions=rejected)
        run.audit_hash = record_agent_audit("workflow.approval", actor=approval.approved_by, run_id=run.id, details=run.to_dict())
        return run
