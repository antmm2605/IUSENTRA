"""Preparazione deposito legale con validazione consapevole."""

from .models import DepositState, PreflightResult, PreflightStatus
from .orchestrator import DepositOrchestrator
from .policies import ChannelProfile, SignaturePolicy, channel_profile_for, get_channel_profile
from .validators import DocumentPreflightValidator

__all__ = [
    "ChannelProfile",
    "DepositOrchestrator",
    "DepositState",
    "DocumentPreflightValidator",
    "PreflightResult",
    "PreflightStatus",
    "SignaturePolicy",
    "channel_profile_for",
    "get_channel_profile",
]
