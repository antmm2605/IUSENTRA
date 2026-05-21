import pytest

from lex.agents.planner import AgentPlanRequest, WorkflowAgentPlanner


def test_planner_costruisce_piano_da_ricetta_reale():
    plan = WorkflowAgentPlanner().build_plan(
        AgentPlanRequest(workflow_code="triage_giornaliero", actor="pytest", fascicolo_id="F1")
    )

    assert plan.workflow_code == "triage_giornaliero"
    assert len(plan.steps) >= 5
    assert any(step.tool_name == "fascicolo" and not step.mutates_state for step in plan.steps)
    assert any(step.tool_name == "create_task" and step.mutates_state for step in plan.steps)
    assert plan.baseline_minutes > plan.expected_review_minutes


def test_planner_non_accetta_workflow_non_registrati():
    with pytest.raises(KeyError):
        WorkflowAgentPlanner().build_plan(AgentPlanRequest(workflow_code="inventato", actor="pytest"))

