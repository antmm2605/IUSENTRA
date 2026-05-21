from lex.agents.metrics import calculate_agent_metric, calculate_run_metric
from lex.agents.models import AgentPlan, AgentRun, AgentStep


def test_metriche_target_ottanta_per_cento():
    metric = calculate_agent_metric(
        workflow_code="triage_giornaliero",
        run_id="run-1",
        baseline_minutes=100,
        review_minutes=15,
        correction_minutes=5,
    )

    assert metric.saved_minutes == 80
    assert metric.saving_percentage == 80
    assert metric.target_80_met is True


def test_metriche_sotto_target_non_forzano_esito_positivo():
    metric = calculate_agent_metric(
        workflow_code="billing_monthly",
        run_id="run-2",
        baseline_minutes=100,
        review_minutes=30,
        correction_minutes=10,
    )

    assert metric.saved_minutes == 60
    assert metric.saving_percentage == 60
    assert metric.target_80_met is False


def test_metriche_run_usano_step_e_penalizzano_blocchi():
    plan = AgentPlan(
        workflow_code="predeposito",
        title="Predeposito",
        description="Test",
        steps=[
            AgentStep(step_key="read", title="Legge", tool_name="fascicolo", status="done", baseline_minutes=40, preview_minutes=2),
            AgentStep(step_key="write", title="Propone", tool_name="update_checklist", mutates_state=True, status="blocked", baseline_minutes=60, review_minutes=30, correction_minutes=10),
        ],
        baseline_minutes=100,
        expected_review_minutes=30,
        expected_correction_minutes=10,
    )
    run = AgentRun(workflow_code="predeposito", created_by="pytest", tenant_scope="studio-a", plan=plan)

    metric = calculate_run_metric(run, rejected_actions=5)

    assert metric.baseline_minutes == 100
    assert metric.preview_minutes == 2
    assert metric.saving_percentage == 40
    assert metric.target_80_met is False
