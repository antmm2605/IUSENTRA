"""Normalizzazione requisiti pratica."""

from __future__ import annotations

from .models import PracticeProfile, PracticeRequirement


def blocking_requirements(profile: PracticeProfile) -> list[PracticeRequirement]:
    return [item for item in profile.required_documents + profile.checklist_items if item.required and item.blocking]


def warning_requirements(profile: PracticeProfile) -> list[PracticeRequirement]:
    return [item for item in profile.required_documents + profile.checklist_items if not item.blocking]
