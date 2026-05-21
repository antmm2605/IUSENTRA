"""Runtime applicativo per API e UI Regia Agentica Studio."""

from __future__ import annotations

from typing import Any, Iterable

from .approvals import mark_rejected
from .audit import record_agent_audit
from .executor import WorkflowAgentExecutor
from .metrics import calculate_run_metric
from .models import AgentApproval, AgentRun, utc_now_iso
from .planner import AgentPlanRequest, WorkflowAgentPlanner
from .policies import WorkflowAgentPolicyError, assert_permissions, assert_tenant_context, validate_client_payload
from .registry import WorkflowRecipeRegistry
from .serialization import public_dict
from .storage import WorkflowAgentStorage
from .synthesis import build_run_result


class WorkflowAgentRuntime:
    def __init__(
        self,
        *,
        storage: WorkflowAgentStorage | None = None,
        planner: WorkflowAgentPlanner | None = None,
        executor: WorkflowAgentExecutor | None = None,
        recipes: WorkflowRecipeRegistry | None = None,
    ):
        self.storage = storage or WorkflowAgentStorage()
        self.recipes = recipes or WorkflowRecipeRegistry()
        self.planner = planner or WorkflowAgentPlanner(self.recipes)
        self.executor = executor or WorkflowAgentExecutor()

    def list_workflows(self) -> list[dict[str, Any]]:
        return [recipe.to_public_dict() for recipe in self.recipes.list_recipes()]

    def latest_runs(self, *, limit: int = 8) -> list[dict[str, Any]]:
        return [public_dict(run) for run in self.storage.list_runs(limit=limit)]

    def preview(
        self,
        payload: dict[str, Any],
        *,
        actor: str,
        tenant_scope: str,
        user_permissions: Iterable[str] | None,
    ) -> AgentRun:
        assert_tenant_context(tenant_scope)
        validate_client_payload(payload)
        workflow_code = str(payload.get("workflow_code") or "").strip()
        if not workflow_code:
            raise WorkflowAgentPolicyError("workflow_required", "Seleziona un percorso agentico.", status_code=400)
        plan = self.planner.build_plan(
            AgentPlanRequest(
                workflow_code=workflow_code,
                actor=actor,
                fascicolo_id=str(payload.get("fascicolo_id") or "").strip(),
                input_text=str(payload.get("input") or payload.get("query") or "").strip(),
                params=dict(payload.get("params") or {}),
            )
        )
        run = AgentRun(
            workflow_code=workflow_code,
            created_by=actor,
            tenant_scope=tenant_scope,
            fascicolo_id=plan.fascicolo_id,
            plan=plan,
            risk_level=plan.risk_level,
            confidence=plan.confidence,
        )
        run = self.executor.preview(run, tenant_scope=tenant_scope, user_permissions=user_permissions)
        self.storage.save_run(run)
        if run.metrics:
            self.storage.save_metric(run.metrics)
        return run

    def get_run(self, run_id: str) -> AgentRun:
        return self.storage.get_run(run_id)

    def list_approvals(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for run in self.storage.list_runs(limit=100):
            for proposal in run.proposals:
                if proposal.status == "pending":
                    item = public_dict(proposal)
                    item["run_id"] = run.id
                    item["workflow_code"] = run.workflow_code
                    item["fascicolo_id"] = run.fascicolo_id
                    item["created_by"] = run.created_by
                    rows.append(item)
        return rows

    def approve(
        self,
        run_id: str,
        payload: dict[str, Any],
        *,
        actor: str,
        tenant_scope: str,
        write_feature_enabled: bool,
        user_permissions: Iterable[str] | None,
    ) -> AgentRun:
        assert_tenant_context(tenant_scope)
        validate_client_payload(payload)
        assert_permissions(("legal_skills.approva",), user_permissions)
        run = self.storage.get_run(run_id)
        approval = AgentApproval(
            run_id=run.id,
            approved_step_ids=[str(item) for item in payload.get("approved_step_ids") or []],
            approved_by=actor,
            modifications=dict(payload.get("modifications") or {}),
            note=str(payload.get("note") or "").strip(),
        )
        record_agent_audit("workflow.approval.requested", actor=actor, run_id=run.id, details=approval.to_dict())
        run = self.executor.execute_approved(
            run,
            approval,
            tenant_scope=tenant_scope,
            write_feature_enabled=write_feature_enabled,
            user_permissions=user_permissions,
        )
        self.storage.save_run(run)
        if run.metrics:
            self.storage.save_metric(run.metrics)
        return run

    def reject(self, run_id: str, payload: dict[str, Any], *, actor: str) -> AgentRun:
        validate_client_payload(payload)
        run = self.storage.get_run(run_id)
        rejected_ids = {str(item) for item in payload.get("rejected_step_ids") or []}
        reason = str(payload.get("reason") or "").strip()
        if not rejected_ids:
            rejected_ids = {proposal.step_id for proposal in run.proposals if proposal.status == "pending"}
        for proposal in run.proposals:
            if proposal.step_id in rejected_ids or proposal.id in rejected_ids:
                mark_rejected(proposal, actor=actor, reason=reason)
        rejected = sum(1 for proposal in run.proposals if proposal.status == "rejected")
        accepted = sum(1 for proposal in run.proposals if proposal.status == "executed")
        run.metrics = calculate_run_metric(run, accepted_actions=accepted, rejected_actions=rejected)
        run.status = "cancelled" if rejected and not accepted else run.status
        run.completed_at = utc_now_iso()
        run.result_json = build_run_result(run)
        run.audit_hash = record_agent_audit("workflow.rejected", actor=actor, run_id=run.id, details={"reason": reason, "rejected": list(rejected_ids)})
        self.storage.save_run(run)
        if run.metrics:
            self.storage.save_metric(run.metrics)
        return run

    def metrics_summary(self) -> dict[str, Any]:
        metrics = self.storage.list_metrics(limit=500)
        if not metrics:
            return {
                "run_count": 0,
                "average_saving_percentage": 0.0,
                "saved_minutes": 0.0,
                "target_80_met": False,
                "accepted_actions": 0,
                "rejected_actions": 0,
                "top_workflows": [],
            }
        total_saved = round(sum(item.saved_minutes for item in metrics), 2)
        average = round(sum(item.saving_percentage for item in metrics) / len(metrics), 2)
        by_workflow: dict[str, list[Any]] = {}
        for item in metrics:
            by_workflow.setdefault(item.workflow_code, []).append(item)
        top = []
        for code, rows in by_workflow.items():
            top.append(
                {
                    "workflow_code": code,
                    "run_count": len(rows),
                    "average_saving_percentage": round(sum(row.saving_percentage for row in rows) / len(rows), 2),
                    "saved_minutes": round(sum(row.saved_minutes for row in rows), 2),
                }
            )
        return {
            "run_count": len(metrics),
            "average_saving_percentage": average,
            "saved_minutes": total_saved,
            "target_80_met": average >= 80.0,
            "accepted_actions": sum(item.accepted_actions for item in metrics),
            "rejected_actions": sum(item.rejected_actions for item in metrics),
            "top_workflows": sorted(top, key=lambda row: row["average_saving_percentage"], reverse=True),
        }
