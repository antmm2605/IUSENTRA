"""Predeposito: controlli separati dall'invio reale."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from .models import SlotStatus, SlotType, ValidatorStatus
from .repository import PracticeEngineRepository
from .validators import ValidationContext, run_validators, validate_slot


NEGATIVE_DEPOSIT_HINTS = (
    "ricevuta",
    "accettazione",
    "consegna",
    "rdac",
    "rac",
    "esito",
    "cancelleria",
    "comunicazione",
    "posta certificata",
    "pec",
)

MAIN_ACT_HINTS = (
    "atto",
    "ricorso",
    "citazione",
    "comparsa",
    "memoria",
    "istanza",
    "opposizione",
    "appello",
    "reclamo",
    "deduzioni",
)


def _notification_proof_hint(text: str) -> bool:
    return any(
        hint in text
        for hint in (
            "notifica",
            "notificazione",
            "originale notificato",
            "notifica id",
            "legge n 53",
            "legge 53",
            "l 53",
            "relata",
            "accettazione",
            "consegna",
            "rac",
            "rdac",
            "pec inviata",
        )
    )


def _slug(value: Any) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text)).strip()


def _document_text(doc: Any) -> str:
    return _slug(
        " ".join(
            str(getattr(doc, field, "") or "")
            for field in (
                "tipo",
                "nome",
                "nome_originale",
                "nome_portale",
                "tipo_atto_portale",
                "classificazione_portale",
                "note",
            )
        )
    )


def _is_signed(doc: Any) -> bool:
    name = str(getattr(doc, "nome", "") or "").lower()
    return bool(
        getattr(doc, "firmato", False)
        or getattr(doc, "firmato_digitalmente", False)
        or name.endswith(".p7m")
    )


def _score_for_slot(slot: Any, doc: Any) -> int:
    text = _document_text(doc)
    slot_text = _slug(f"{getattr(slot, 'slot_key', '')} {getattr(slot, 'label', '')} {getattr(slot, 'type', '')}")
    if not text:
        return 0
    negative = any(hint in text for hint in NEGATIVE_DEPOSIT_HINTS)
    score = 0
    slot_type = str(getattr(slot, "type", "") or "").upper()
    if slot_type == SlotType.ATTO_PRINCIPALE.value or "atto principale" in slot_text:
        if negative or any(hint in text for hint in ("procura", "contributo", "pagopa", "marca", "nir", "nota iscrizione")):
            return 0
        score += 50 if any(hint in text for hint in MAIN_ACT_HINTS) else 0
        score += 20 if any(hint in text for hint in ("atto giudiziario", "comparsa", "ricorso", "memoria")) else 0
        score += 5 if _is_signed(doc) else 0
        return score
    if slot_type == SlotType.PROCURA.value or "procura" in slot_text:
        return 90 if "procura" in text else 0
    if slot_type == SlotType.CONTRIBUTO_UNIFICATO.value or any(hint in slot_text for hint in ("contributo", "pagamento", "pagopa")):
        return 90 if any(hint in text for hint in ("contributo", "unificato", "pagopa", "rt xml", "ricevuta telematica")) else 0
    if slot_type == SlotType.MARCA_BOLLO.value or "marca" in slot_text:
        return 85 if any(hint in text for hint in ("marca", "bollo")) else 0
    if slot_type == SlotType.NOTA_ISCRIZIONE_RUOLO.value or any(hint in slot_text for hint in ("nir", "nota iscrizione")):
        return 95 if any(hint in text for hint in ("nir", "nota iscrizione", "iscrizione a ruolo")) else 0
    if slot_type == SlotType.PROVVEDIMENTO.value or any(hint in slot_text for hint in ("provvedimento", "sentenza", "ordinanza", "decreto")):
        return 75 if any(hint in text for hint in ("provvedimento", "sentenza", "ordinanza", "decreto")) else 0
    if slot_type in {SlotType.RICEVUTA.value, SlotType.COMUNICAZIONE.value}:
        return 70 if negative else 0
    if slot_type in {
        SlotType.ALLEGATO.value,
        SlotType.DOCUMENTO_PROVA.value,
        SlotType.DOCUMENTO_CLIENTE.value,
        SlotType.DOCUMENTO_CONTROPARTE.value,
    }:
        if slot_type == SlotType.DOCUMENTO_PROVA.value and any(hint in slot_text for hint in ("prova", "notifica", "ricevuta")):
            return 85 if _notification_proof_hint(text) else 0
        if negative:
            return 0
        if any(hint in text for hint in ("procura", "contributo", "pagopa", "nir", "nota iscrizione")):
            return 0
        return 35 if any(hint in text for hint in ("allegato", "documento", "contratto", "quietanza", "prova")) else 10
    return 0


def _auto_link_threshold(slot: Any) -> int:
    slot_type = str(getattr(slot, "type", "") or "").upper()
    slot_text = _slug(f"{getattr(slot, 'slot_key', '')} {getattr(slot, 'label', '')}")
    if slot_type == SlotType.ATTO_PRINCIPALE.value or "atto principale" in slot_text:
        return 70
    if slot_type in {
        SlotType.PROCURA.value,
        SlotType.CONTRIBUTO_UNIFICATO.value,
        SlotType.MARCA_BOLLO.value,
        SlotType.NOTA_ISCRIZIONE_RUOLO.value,
    }:
        return 85
    if slot_type == SlotType.PROVVEDIMENTO.value:
        return 75
    if slot_type in {SlotType.RICEVUTA.value, SlotType.COMUNICAZIONE.value}:
        return 75
    return 80


def _auto_link_deposit_slots(
    repository: PracticeEngineRepository,
    *,
    fascicolo_id: str,
    slots: list[Any],
    documents: list[Any],
) -> list[Any]:
    used_ids = {
        str(getattr(slot, "document_id", "") or "").strip()
        for slot in slots
        if str(getattr(slot, "document_id", "") or "").strip()
    }
    changed = False
    updated_slots = list(slots)
    for index, slot in enumerate(list(updated_slots)):
        if str(getattr(slot, "document_id", "") or "").strip() or not getattr(slot, "required", False):
            continue
        threshold = _auto_link_threshold(slot)
        candidates: list[tuple[int, Any]] = []
        for doc in documents:
            doc_id = str(getattr(doc, "id", "") or "").strip()
            if not doc_id or doc_id in used_ids:
                continue
            score = _score_for_slot(slot, doc)
            if score >= threshold:
                candidates.append((score, doc))
        if not candidates:
            continue
        candidates.sort(
            key=lambda item: (
                item[0],
                int(getattr(item[1], "dimensione_bytes", 0) or 0),
                str(getattr(item[1], "data_caricamento", "") or ""),
            ),
            reverse=True,
        )
        selected = candidates[0][1]
        selected_id = str(getattr(selected, "id", "") or "").strip()
        if not selected_id:
            continue
        slot.document_id = selected_id
        slot.status = SlotStatus.DA_VALIDARE.value
        slot.message = "Documento proposto automaticamente dal fascicolo."
        slot.suggested_action = "Verifica la proposta; se corretta, prosegui con il controllo di deposito."
        repository.upsert_slot(slot)
        repository.audit(
            fascicolo_id,
            "DOCUMENT_SLOT_AUTO_LINKED",
            message=f"Slot {slot.slot_key} collegato automaticamente al documento {selected_id}.",
            payload={"slot_key": slot.slot_key, "document_id": selected_id},
        )
        used_ids.add(selected_id)
        updated_slots[index] = slot
        changed = True
    return repository.list_slots(fascicolo_id) if changed else updated_slots


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
    slots = _auto_link_deposit_slots(
        repository,
        fascicolo_id=fascicolo_id,
        slots=slots,
        documents=list(getattr(fascicolo, "documenti", []) or []),
    )
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
