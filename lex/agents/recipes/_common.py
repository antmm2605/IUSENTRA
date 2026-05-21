from __future__ import annotations

from typing import Any

from ..models import AgentPlan, AgentStep
from ..policies import required_permissions_for_tool


def text(payload: dict[str, Any], key: str, default: str = "") -> str:
    value = payload.get("params", {}).get(key)
    if value in (None, ""):
        value = payload.get(key, default)
    return str(value if value is not None else default).strip()


def readonly_step(
    key: str,
    title: str,
    tool_name: str,
    input_json: dict[str, Any] | None = None,
    *,
    minutes: float = 0.0,
    confidence: float = 0.75,
) -> AgentStep:
    return AgentStep(
        step_key=key,
        title=title,
        tool_name=tool_name,
        input_json=input_json or {},
        required_permissions=required_permissions_for_tool(tool_name),
        baseline_minutes=minutes,
        preview_minutes=min(minutes, 2.0),
        confidence=confidence,
    )


def write_step(
    key: str,
    title: str,
    tool_name: str,
    input_json: dict[str, Any],
    *,
    minutes: float,
    risk: str = "medium",
    confidence: float = 0.7,
) -> AgentStep:
    return AgentStep(
        step_key=key,
        title=title,
        tool_name=tool_name,
        input_json=input_json,
        mutates_state=True,
        approval_required=True,
        required_permissions=required_permissions_for_tool(tool_name, mutates_state=True),
        baseline_minutes=minutes,
        review_minutes=max(1.0, round(minutes * 0.15, 2)),
        correction_minutes=max(0.5, round(minutes * 0.05, 2)),
        risk_level=risk,
        confidence=confidence,
    )


def plan(
    *,
    workflow_code: str,
    title: str,
    description: str,
    steps: list[AgentStep],
    baseline_minutes: float,
    expected_review_minutes: float,
    expected_correction_minutes: float,
    risk_level: str,
    fascicolo_id: str = "",
    confidence: float = 0.75,
    warnings: list[str] | None = None,
) -> AgentPlan:
    return AgentPlan(
        workflow_code=workflow_code,
        title=title,
        description=description,
        steps=steps,
        baseline_minutes=baseline_minutes,
        expected_review_minutes=expected_review_minutes,
        expected_correction_minutes=expected_correction_minutes,
        risk_level=risk_level,
        fascicolo_id=fascicolo_id,
        confidence=confidence,
        warnings=warnings or [],
    )

