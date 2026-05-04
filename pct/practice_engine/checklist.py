"""Checklist dinamiche generate dal profilo pratica."""

from __future__ import annotations

from .models import ChecklistItem, PracticeProfile
from .repository import PracticeEngineRepository


def ensure_checklist(repository: PracticeEngineRepository, fascicolo_id: str, profile: PracticeProfile) -> list[ChecklistItem]:
    return repository.ensure_checklist(fascicolo_id, profile)
