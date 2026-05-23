"""Planner deterministico basato su ricette approvate."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import AgentPlan
from .policies import validate_client_payload
from .registry import WorkflowRecipeRegistry


@dataclass(slots=True)
class AgentPlanRequest:
    workflow_code: str
    actor: str
    fascicolo_id: str = ""
    input_text: str = ""
    params: dict[str, Any] = field(default_factory=dict)


class WorkflowAgentPlanner:
    def __init__(self, recipes: WorkflowRecipeRegistry | None = None):
        self.recipes = recipes or WorkflowRecipeRegistry()

    def build_plan(self, request: AgentPlanRequest) -> AgentPlan:
        payload = {
            "workflow_code": request.workflow_code,
            "fascicolo_id": request.fascicolo_id,
            "input_text": request.input_text,
            "params": request.params,
            "actor": request.actor,
        }
        validate_client_payload(payload)
        recipe = self.recipes.get(request.workflow_code)
        plan = recipe.builder(payload)
        plan.workflow_code = recipe.code
        plan.title = recipe.title
        plan.description = recipe.description
        plan.risk_level = recipe.risk_level
        plan.baseline_minutes = recipe.baseline_minutes
        if request.fascicolo_id and not plan.fascicolo_id:
            plan.fascicolo_id = request.fascicolo_id
        return plan
