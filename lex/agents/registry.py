"""Registro ricette agentiche governate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .models import AgentPlan


RecipeBuilder = Callable[[dict[str, Any]], AgentPlan]


@dataclass(frozen=True, slots=True)
class WorkflowRecipe:
    code: str
    title: str
    description: str
    risk_level: str
    baseline_minutes: float
    builder: RecipeBuilder

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "title": self.title,
            "description": self.description,
            "risk_level": self.risk_level,
            "baseline_minutes": self.baseline_minutes,
        }


def _load_recipes() -> dict[str, WorkflowRecipe]:
    from .recipes.billing_monthly import recipe as billing_monthly
    from .recipes.legal_research import recipe as legal_research
    from .recipes.nuovo_incarico import recipe as nuovo_incarico
    from .recipes.predeposito import recipe as predeposito
    from .recipes.redazione_atto import recipe as redazione_atto
    from .recipes.triage_giornaliero import recipe as triage_giornaliero

    rows = [
        triage_giornaliero(),
        redazione_atto(),
        billing_monthly(),
        nuovo_incarico(),
        predeposito(),
        legal_research(),
    ]
    return {row.code: row for row in rows}


class WorkflowRecipeRegistry:
    def __init__(self):
        self._recipes = _load_recipes()

    def list_recipes(self) -> list[WorkflowRecipe]:
        return [self._recipes[key] for key in sorted(self._recipes)]

    def get(self, code: str) -> WorkflowRecipe:
        recipe = self._recipes.get(str(code or "").strip())
        if not recipe:
            raise KeyError("Workflow agentico non registrato.")
        return recipe
