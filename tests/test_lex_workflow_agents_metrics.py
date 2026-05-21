from lex.agents.metrics import calculate_agent_metric


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

