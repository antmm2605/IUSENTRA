"""Dominio minimale del bounded context Lex."""

from .confidence import compute_confidence
from .risk import classify_risk

__all__ = ["classify_risk", "compute_confidence"]
