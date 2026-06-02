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
from .payment_policies import (
    PaymentPolicy,
    list_payment_policies,
    payment_policy_for_channel,
    payment_policy_for_procedure,
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
    "PaymentPolicy",
    "SignaturePolicy",
    "TelematicProcedure",
    "UnknownChannelError",
    "UnknownProcedureError",
    "channel_profile_for",
    "get_channel_profile",
    "list_payment_policies",
    "get_procedure",
    "payment_policy_for_channel",
    "payment_policy_for_procedure",
    "list_procedures",
    "validate_procedure_profile",
]
