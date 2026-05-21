import pytest

from lex.agents.executor import WorkflowAgentExecutor
from lex.agents.models import AgentApproval, AgentPlan, AgentRun, AgentStep
from lex.agents.policies import WorkflowAgentPolicyError


class FakeRegistry:
    def __init__(self):
        self.calls = []

    def run_tool(self, tool_name, **kwargs):
        self.calls.append((tool_name, kwargs))
        return {"ok": True, "tool": tool_name}


def _run():
    read = AgentStep(
        step_key="read",
        title="Legge fascicolo",
        tool_name="fascicolo",
        required_permissions=("fascicoli.leggi",),
    )
    write = AgentStep(
        step_key="write",
        title="Crea task",
        tool_name="create_task",
        mutates_state=True,
        approval_required=True,
        required_permissions=("agenda.scrivi",),
        input_json={"titolo": "Verifica urgente"},
    )
    plan = AgentPlan(
        workflow_code="triage_giornaliero",
        title="Triage",
        description="Test",
        steps=[read, write],
        baseline_minutes=100,
        expected_review_minutes=15,
        expected_correction_minutes=5,
    )
    return AgentRun(workflow_code="triage_giornaliero", created_by="pytest", tenant_scope="studio-a", plan=plan)


def test_preview_esegue_solo_letture_e_mette_scritture_in_approvazione():
    registry = FakeRegistry()
    run = WorkflowAgentExecutor(registry).preview(
        _run(),
        tenant_scope="studio-a",
        user_permissions=["fascicoli.leggi", "agenda.scrivi"],
    )

    assert [call[0] for call in registry.calls] == ["fascicolo"]
    assert run.status == "needs_approval"
    assert run.proposals
    assert run.plan.steps[1].status == "needs_approval"


def test_approve_blocca_permessi_mancanti():
    run = WorkflowAgentExecutor(FakeRegistry()).preview(
        _run(),
        tenant_scope="studio-a",
        user_permissions=["fascicoli.leggi", "agenda.scrivi"],
    )

    with pytest.raises(WorkflowAgentPolicyError) as exc:
        WorkflowAgentExecutor(FakeRegistry()).execute_approved(
            run,
            AgentApproval(run_id=run.id, approved_step_ids=[run.plan.steps[1].id], approved_by="pytest"),
            tenant_scope="studio-a",
            write_feature_enabled=True,
            user_permissions=["fascicoli.leggi"],
        )

    assert exc.value.code == "insufficient_permissions"


def test_approve_con_permesso_esegue_tool_mutante():
    registry = FakeRegistry()
    executor = WorkflowAgentExecutor(registry)
    run = executor.preview(_run(), tenant_scope="studio-a", user_permissions=["fascicoli.leggi", "agenda.scrivi"])
    updated = executor.execute_approved(
        run,
        AgentApproval(run_id=run.id, approved_step_ids=[run.plan.steps[1].id], approved_by="pytest"),
        tenant_scope="studio-a",
        write_feature_enabled=True,
        user_permissions=["agenda.scrivi"],
    )

    assert updated.status == "executed"
    assert registry.calls[-1][0] == "create_task"
    assert updated.metrics and updated.metrics.target_80_met is True

