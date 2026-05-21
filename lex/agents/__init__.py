"""Lex Workflow Agents: regia agentica governata per IUSENTRA."""

from typing import TYPE_CHECKING, Any

from .metrics import calculate_agent_metric, calculate_run_metric
from .models import AgentApproval, AgentMetric, AgentPlan, AgentProposal, AgentRun, AgentStep

if TYPE_CHECKING:
    from .executor import WorkflowAgentExecutor
    from .planner import AgentPlanRequest, WorkflowAgentPlanner
    from .registry import WorkflowRecipeRegistry
    from .runtime import WorkflowAgentRuntime


_LAZY_EXPORTS = {
    "AgentPlanRequest": (".planner", "AgentPlanRequest"),
    "WorkflowAgentExecutor": (".executor", "WorkflowAgentExecutor"),
    "WorkflowAgentPlanner": (".planner", "WorkflowAgentPlanner"),
    "WorkflowAgentRuntime": (".runtime", "WorkflowAgentRuntime"),
    "WorkflowRecipeRegistry": (".registry", "WorkflowRecipeRegistry"),
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(name)
    module_name, attr_name = _LAZY_EXPORTS[name]
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), attr_name)
    globals()[name] = value
    return value

__all__ = [
    "AgentApproval",
    "AgentMetric",
    "AgentPlan",
    "AgentPlanRequest",
    "AgentProposal",
    "AgentRun",
    "AgentStep",
    "WorkflowAgentExecutor",
    "WorkflowAgentPlanner",
    "WorkflowAgentRuntime",
    "WorkflowRecipeRegistry",
    "calculate_agent_metric",
    "calculate_run_metric",
]
