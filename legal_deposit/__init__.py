"""Preparazione deposito legale con validazione consapevole."""

from .models import DepositState, PreflightResult, PreflightStatus
from .orchestrator import DepositOrchestrator
from .policies import (
    AmbiguousChannelError,
    ChannelProfile,
    SignaturePolicy,
    UnknownChannelError,
    channel_profile_for,
    get_channel_profile,
)
from .procedure_registry import (
    ProcedureProfileMismatchError,
    TelematicProcedure,
    UnknownProcedureError,
    get_procedure,
    list_procedures,
    validate_procedure_profile,
)
from .validators import DocumentPreflightValidator

__all__ = [
    "ChannelProfile",
    "DepositOrchestrator",
    "DepositState",
    "DocumentPreflightValidator",
    "AmbiguousChannelError",
    "ProcedureProfileMismatchError",
    "PreflightResult",
    "PreflightStatus",
    "SignaturePolicy",
    "TelematicProcedure",
    "UnknownChannelError",
    "UnknownProcedureError",
    "channel_profile_for",
    "get_channel_profile",
    "get_procedure",
    "list_procedures",
    "validate_procedure_profile",
]
