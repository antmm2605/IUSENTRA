"""Façade stabile per template lifecycle procedurali.

Il generatore resta in `pct.procedure_lifecycle`; questo modulo fornisce il
nome applicativo richiesto senza duplicare step o regole.
"""

from __future__ import annotations

from pct.procedure_lifecycle import (
    LIFECYCLE_STEP_TYPES,
    STEP_LABELS,
    LifecycleStepType,
    build_lifecycle_steps_for_xsd,
    generate_lifecycle_template_for_xsd,
    generate_lifecycle_templates_for_catalog,
)

__all__ = [
    "LIFECYCLE_STEP_TYPES",
    "STEP_LABELS",
    "LifecycleStepType",
    "build_lifecycle_steps_for_xsd",
    "generate_lifecycle_template_for_xsd",
    "generate_lifecycle_templates_for_catalog",
]
