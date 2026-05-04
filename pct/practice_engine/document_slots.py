"""Slot documentali persistenti e collegabili ai Documenti fascicolo."""

from __future__ import annotations

from .models import DocumentSlot, PracticeProfile
from .repository import PracticeEngineRepository


def ensure_document_slots(repository: PracticeEngineRepository, fascicolo_id: str, profile: PracticeProfile) -> list[DocumentSlot]:
    return repository.ensure_slots(fascicolo_id, profile)


def link_document_slot(
    repository: PracticeEngineRepository,
    fascicolo_id: str,
    slot_key: str,
    document_id: str,
    *,
    actor: str = "",
) -> DocumentSlot:
    return repository.link_slot(fascicolo_id, slot_key, document_id, actor=actor)
