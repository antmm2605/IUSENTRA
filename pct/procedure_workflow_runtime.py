"""Façade stabile per runtime workflow fascicolo.

La state machine resta in `pct.procedure_lifecycle`, così il lifecycle pratica
usa un solo motore e un solo audit.
"""

from __future__ import annotations

from pct.procedure_lifecycle import (
    ALLOWED_TRANSITIONS,
    WORKFLOW_STATES,
    WorkflowState,
    open_workflow_instance,
    transition_workflow,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "WORKFLOW_STATES",
    "WorkflowState",
    "open_workflow_instance",
    "transition_workflow",
]
