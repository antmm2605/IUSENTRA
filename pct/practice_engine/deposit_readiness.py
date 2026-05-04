"""Predeposito: controlli separati dall'invio reale."""

from __future__ import annotations

from typing import Any

from .models import ValidatorStatus
from .repository import PracticeEngineRepository
from .validators import ValidationContext, run_validators, validate_slot


def run_predeposit_check(
    repository: PracticeEngineRepository,
    *,
    fascicolo: Any,
    profile: Any,
    cliente: Any | None = None,
    preventivo: Any | None = None,
    conferimento: Any | None = None,
    parcelle: list[Any] | None = None,
    fascicoli_manager: Any | None = None,
    deposito_session: Any | None = None,
) -> dict[str, Any]:
    fascicolo_id = str(getattr(fascicolo, "id", "") or "")
    slots = repository.ensure_slots(fascicolo_id, profile)
    audit_events = repository.list_audit(fascicolo_id)
    ctx = ValidationContext(
        fascicolo=fascicolo,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        parcelle=list(parcelle or []),
        slots=slots,
        fascicoli_manager=fascicoli_manager,
        profile=profile,
        audit_events=audit_events,
        deposito_session=deposito_session,
    )
    slot_results = []
    updated_slots = []
    for slot in slots:
        if slot.required or slot.document_id:
            updated, results = validate_slot(slot, ctx)
            repository.upsert_slot(updated)
            repository.save_validation_results(fascicolo_id, results, scope="slot", slot_key=slot.slot_key)
            updated_slots.append(updated)
            slot_results.extend(results)
    general_keys = list(dict.fromkeys((profile.blocking_validators or []) + (profile.warning_validators or [])))
    general_results = run_validators(general_keys, ctx)
    repository.save_validation_results(fascicolo_id, general_results, scope="predeposito")
    all_results = general_results + slot_results
    blockers = [item for item in all_results if item.status in {ValidatorStatus.BLOCK.value, ValidatorStatus.ERROR.value}]
    warnings = [item for item in all_results if item.status == ValidatorStatus.WARNING.value]
    pending = [item for item in all_results if item.status == ValidatorStatus.PENDING.value]
    status = "OK" if not blockers and not pending else ("BLOCCANTE" if blockers else "DA_COMPLETARE")
    return {
        "status": status,
        "ready": status == "OK",
        "blockers": [item for item in blockers],
        "warnings": [item for item in warnings],
        "pending": [item for item in pending],
        "results": all_results,
        "slots": updated_slots or slots,
    }
