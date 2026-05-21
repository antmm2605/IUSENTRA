"""Metriche di risparmio tempo dei workflow agentici."""

from __future__ import annotations

from .models import AgentMetric


TARGET_SAVING_PERCENTAGE = 80.0


def calculate_agent_metric(
    *,
    workflow_code: str,
    run_id: str,
    baseline_minutes: float,
    review_minutes: float,
    correction_minutes: float = 0.0,
    preview_minutes: float = 0.0,
    accepted_actions: int = 0,
    rejected_actions: int = 0,
) -> AgentMetric:
    baseline = max(float(baseline_minutes or 0.0), 0.0)
    review = max(float(review_minutes or 0.0), 0.0)
    correction = max(float(correction_minutes or 0.0), 0.0)
    if baseline <= 0:
        saved = 0.0
        percentage = 0.0
    else:
        saved = max(baseline - review - correction, 0.0)
        percentage = round((saved / baseline) * 100.0, 2)
    return AgentMetric(
        workflow_code=workflow_code,
        run_id=run_id,
        baseline_minutes=round(baseline, 2),
        preview_minutes=round(max(float(preview_minutes or 0.0), 0.0), 2),
        review_minutes=round(review, 2),
        correction_minutes=round(correction, 2),
        saved_minutes=round(saved, 2),
        saving_percentage=percentage,
        target_80_met=percentage >= TARGET_SAVING_PERCENTAGE,
        accepted_actions=int(accepted_actions or 0),
        rejected_actions=int(rejected_actions or 0),
    )


def calculate_run_metric(
    run,
    *,
    accepted_actions: int = 0,
    rejected_actions: int = 0,
) -> AgentMetric:
    """Calcola il KPI dal piano e dallo stato effettivo del run."""
    steps = list(getattr(getattr(run, "plan", None), "steps", []) or [])
    baseline = sum(float(getattr(step, "baseline_minutes", 0.0) or 0.0) for step in steps)
    if baseline <= 0:
        baseline = float(getattr(getattr(run, "plan", None), "baseline_minutes", 0.0) or 0.0)

    preview = sum(
        float(getattr(step, "preview_minutes", 0.0) or 0.0)
        for step in steps
        if not bool(getattr(step, "mutates_state", False)) and getattr(step, "status", "") == "done"
    )
    review_from_steps = sum(
        float(getattr(step, "review_minutes", 0.0) or 0.0)
        for step in steps
        if bool(getattr(step, "mutates_state", False))
    )
    correction_from_steps = sum(
        float(getattr(step, "correction_minutes", 0.0) or 0.0)
        for step in steps
        if getattr(step, "status", "") in {"blocked", "failed"}
    )
    plan = getattr(run, "plan", None)
    review = max(float(getattr(plan, "expected_review_minutes", 0.0) or 0.0), review_from_steps)
    correction = float(getattr(plan, "expected_correction_minutes", 0.0) or 0.0) + correction_from_steps
    correction += max(int(rejected_actions or 0), 0) * 2.0
    return calculate_agent_metric(
        workflow_code=str(getattr(run, "workflow_code", "") or ""),
        run_id=str(getattr(run, "id", "") or ""),
        baseline_minutes=baseline,
        preview_minutes=preview,
        review_minutes=review,
        correction_minutes=correction,
        accepted_actions=accepted_actions,
        rejected_actions=rejected_actions,
    )
