"""Ciclo di apprendimento autonomo governato di Lex.

Bounded context "autonomy": rileva lacune, pianifica ricerche, interroga
provider governati, legge fonti ufficiali con cortesia (robots + rate-limit),
aggiorna la memoria e PROPONE miglioramenti con revisione umana obbligatoria.
Non scrive codice, non committa, non pubblica: vedi `lex.autonomy.safety`.
"""

from lex.autonomy.autonomous_cycle import AutonomousLearningCycle, run_autonomous_cycle
from lex.autonomy.discovery import ConfigurableWebSearchProvider, SearchProvider, StaticSearchProvider
from lex.autonomy.models import (
    CycleConfig,
    ImprovementProposal,
    LearningCycleResult,
    ResearchQuestion,
    UnknownConcept,
)
from lex.autonomy.safety import (
    AutonomyViolation,
    CycleConfigError,
    CycleError,
    SourceAccessError,
    refuse_apply,
    validate_cycle_config,
)

__all__ = [
    "AutonomousLearningCycle",
    "AutonomyViolation",
    "ConfigurableWebSearchProvider",
    "CycleConfig",
    "CycleConfigError",
    "CycleError",
    "ImprovementProposal",
    "LearningCycleResult",
    "ResearchQuestion",
    "SearchProvider",
    "SourceAccessError",
    "StaticSearchProvider",
    "UnknownConcept",
    "refuse_apply",
    "run_autonomous_cycle",
    "validate_cycle_config",
]
