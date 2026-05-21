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

