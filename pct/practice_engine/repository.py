"""Repository JSON tenant-aware per Practice Engine.

La persistenza primaria resta nel data root dello studio. Le migrazioni SQL
rendono il dominio governato anche per SQLite/PostgreSQL, ma il runtime
storico di IUSENTRA continua a usare repository JSON sincronizzabili.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any
import json

from .models import (
    AuditEvent,
    ChecklistItem,
    DepositReceipt,
    DepositSession,
    DocumentSlot,
    EvidencePack,
    PracticeProfile,
    PracticeState,
    SlotStatus,
    TimelineEvent,
    ValidationResult,
    dataclass_from_dict,
    new_id,
    utc_now,
)


STORE_KEYS = [
    "practice_profiles",
    "practice_requirements",
    "practice_document_slots",
    "practice_checklist_items",
    "practice_validation_results",
    "practice_state_history",
    "deposit_sessions",
    "deposit_receipts",
    "deposit_timeline_events",
    "evidence_packs",
    "audit_events",
]


class PracticeEngineRepository:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.root_dir = self.db_path.parent
        self.receipts_dir = self.root_dir / "receipts"
        self.evidence_dir = self.root_dir / "evidence_packs"
        for folder in (self.root_dir, self.receipts_dir, self.evidence_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    @classmethod
    def from_fascicoli_db(cls, fascicoli_db_path: str) -> "PracticeEngineRepository":
        base = Path(fascicoli_db_path).parent
        return cls(str(base / "practice_engine" / "practice_engine.json"))

    def _empty(self) -> dict[str, Any]:
        return {key: [] for key in STORE_KEYS}

    def _load(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return self._empty()
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return self._empty()
        except (OSError, json.JSONDecodeError):
            return self._empty()
        data = self._empty()
        for key in STORE_KEYS:
            rows = raw.get(key, [])
            data[key] = rows if isinstance(rows, list) else []
        return data

    def _save(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reload(self) -> None:
        self._data = self._load()

    def apply_profile(
        self,
        fascicolo_id: str,
        profile: PracticeProfile,
        *,
        actor: str = "",
        reason: str = "",
        reset: bool = False,
    ) -> dict[str, Any]:
        fascicolo_id = str(fascicolo_id or "").strip()
        existing = [row for row in self._data["practice_profiles"] if row.get("fascicolo_id") != fascicolo_id]
        snapshot = profile.to_dict()
        snapshot.update({"fascicolo_id": fascicolo_id, "applied_at": utc_now(), "applied_by": actor, "manual_reason": reason})
        existing.append(snapshot)
        self._data["practice_profiles"] = existing
        if reset:
            self._data["practice_document_slots"] = [
                row for row in self._data["practice_document_slots"] if row.get("fascicolo_id") != fascicolo_id
            ]
            self._data["practice_checklist_items"] = [
                row for row in self._data["practice_checklist_items"] if row.get("fascicolo_id") != fascicolo_id
            ]
        self.ensure_slots(fascicolo_id, profile)
        self.ensure_checklist(fascicolo_id, profile)
        self.record_state(fascicolo_id, PracticeState.FASCICOLO_APERTO.value, actor=actor, reason="Profilo pratica applicato.")
        self.audit(fascicolo_id, "PROFILE_APPLIED", actor=actor, message=f"Profilo {profile.code} applicato.", reason=reason, payload={"profile_code": profile.code})
        self._save()
        return snapshot

    def get_profile_snapshot(self, fascicolo_id: str) -> dict[str, Any] | None:
        for row in reversed(self._data["practice_profiles"]):
            if row.get("fascicolo_id") == fascicolo_id:
                return dict(row)
        return None

    def ensure_slots(self, fascicolo_id: str, profile: PracticeProfile) -> list[DocumentSlot]:
        existing = {row.get("slot_key"): row for row in self._data["practice_document_slots"] if row.get("fascicolo_id") == fascicolo_id}
        rows = list(self._data["practice_document_slots"])
        for index, spec in enumerate(profile.required_slots, start=1):
            key = str(spec.get("slot_key") or "").strip().upper()
            if not key or key in existing:
                continue
            slot = DocumentSlot(
                id=new_id("slot"),
                fascicolo_id=fascicolo_id,
                profile_id=profile.code,
                slot_key=key,
                label=str(spec.get("label") or key),
                type=str(spec.get("type") or "ALTRO"),
                required=bool(spec.get("required", True)),
                blocking=bool(spec.get("blocking", True)),
                validators=list(spec.get("validators") or []),
                message=str(spec.get("message") or ""),
                suggested_action=str(spec.get("suggested_action") or ""),
                sort_order=int(spec.get("sort_order") or index),
            )
            rows.append(asdict(slot))
        self._data["practice_document_slots"] = rows
        self._save()
        return self.list_slots(fascicolo_id)

    def ensure_checklist(self, fascicolo_id: str, profile: PracticeProfile) -> list[ChecklistItem]:
        existing = {row.get("key"): row for row in self._data["practice_checklist_items"] if row.get("fascicolo_id") == fascicolo_id}
        rows = list(self._data["practice_checklist_items"])
        for index, item in enumerate(profile.checklist_items, start=1):
            if item.key in existing:
                continue
            rows.append(
                asdict(
                    ChecklistItem(
                        id=new_id("chk"),
                        fascicolo_id=fascicolo_id,
                        profile_id=profile.code,
                        key=item.key,
                        label=item.label,
                        required=item.required,
                        blocking=item.blocking,
                        message=item.message,
                        suggested_action=item.suggested_action,
                        sort_order=index,
                        source=item.source,
                    )
                )
            )
        self._data["practice_checklist_items"] = rows
        self._save()
        return self.list_checklist(fascicolo_id)

    def list_slots(self, fascicolo_id: str) -> list[DocumentSlot]:
        rows = [
            dataclass_from_dict(DocumentSlot, row)
            for row in self._data["practice_document_slots"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: (item.sort_order, item.label))

    def get_slot(self, fascicolo_id: str, slot_key: str) -> DocumentSlot | None:
        key = str(slot_key or "").strip().upper()
        for slot in self.list_slots(fascicolo_id):
            if slot.slot_key.upper() == key:
                return slot
        return None

    def upsert_slot(self, slot: DocumentSlot) -> DocumentSlot:
        rows = [
            row
            for row in self._data["practice_document_slots"]
            if not (row.get("fascicolo_id") == slot.fascicolo_id and row.get("slot_key") == slot.slot_key)
        ]
        rows.append(asdict(slot))
        self._data["practice_document_slots"] = rows
        self._save()
        return slot

    def link_slot(self, fascicolo_id: str, slot_key: str, document_id: str, *, actor: str = "") -> DocumentSlot:
        slot = self.get_slot(fascicolo_id, slot_key)
        if not slot:
            raise KeyError(f"Slot documentale '{slot_key}' non trovato.")
        slot.document_id = str(document_id or "").strip()
        slot.status = SlotStatus.DA_VALIDARE.value if slot.document_id else SlotStatus.MANCANTE.value
        slot.message = "Documento collegato. Ripeti la verifica dello slot."
        slot.suggested_action = "Esegui la validazione dello slot documentale."
        self.upsert_slot(slot)
        self.audit(fascicolo_id, "DOCUMENT_SLOT_LINKED", actor=actor, message=f"Slot {slot.slot_key} collegato al documento {document_id}.")
        return slot

    def list_checklist(self, fascicolo_id: str) -> list[ChecklistItem]:
        rows = [
            dataclass_from_dict(ChecklistItem, row)
            for row in self._data["practice_checklist_items"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: (item.sort_order, item.label))

    def save_validation_results(
        self,
        fascicolo_id: str,
        results: list[ValidationResult],
        *,
        scope: str = "fascicolo",
        slot_key: str = "",
    ) -> list[ValidationResult]:
        rows = [
            row
            for row in self._data["practice_validation_results"]
            if not (row.get("fascicolo_id") == fascicolo_id and row.get("scope") == scope and row.get("slot_key", "") == slot_key)
        ]
        for result in results:
            row = asdict(result)
            row.update({"fascicolo_id": fascicolo_id, "scope": scope, "slot_key": slot_key})
            rows.append(row)
        self._data["practice_validation_results"] = rows
        self._save()
        return results

    def list_validation_results(self, fascicolo_id: str, *, scope: str = "", slot_key: str = "") -> list[ValidationResult]:
        rows: list[ValidationResult] = []
        for row in self._data["practice_validation_results"]:
            if row.get("fascicolo_id") != fascicolo_id:
                continue
            if scope and row.get("scope") != scope:
                continue
            if slot_key and row.get("slot_key", "") != slot_key:
                continue
            rows.append(dataclass_from_dict(ValidationResult, row))
        return rows

    def record_state(self, fascicolo_id: str, state: str, *, actor: str = "", reason: str = "", payload: dict[str, Any] | None = None) -> None:
        self._data["practice_state_history"].append(
            {
                "id": new_id("state"),
                "fascicolo_id": fascicolo_id,
                "state": state,
                "actor": actor,
                "reason": reason,
                "payload": payload or {},
                "created_at": utc_now(),
            }
        )
        self._save()

    def latest_state(self, fascicolo_id: str) -> str:
        for row in reversed(self._data["practice_state_history"]):
            if row.get("fascicolo_id") == fascicolo_id:
                return str(row.get("state") or "")
        return PracticeState.PRE_FASCICOLO.value

    def create_deposit_session(self, fascicolo_id: str, profile_id: str, channel: str, *, status: str, transport_mode: str = "non_configurato", messages: list[str] | None = None) -> DepositSession:
        session = DepositSession(
            id=new_id("dep"),
            fascicolo_id=fascicolo_id,
            profile_id=profile_id,
            channel=channel,
            status=status,
            transport_mode=transport_mode,
            messages=list(messages or []),
        )
        self._data["deposit_sessions"].append(asdict(session))
        self.add_timeline_event(session.id, fascicolo_id, "DEPOSIT_SESSION_CREATED", status, "Sessione deposito creata.")
        self._save()
        return session

    def get_deposit_session(self, deposito_id: str) -> DepositSession | None:
        for row in self._data["deposit_sessions"]:
            if row.get("id") == deposito_id:
                return dataclass_from_dict(DepositSession, row)
        return None

    def update_deposit_session(self, session: DepositSession) -> DepositSession:
        session.updated_at = utc_now()
        rows = [row for row in self._data["deposit_sessions"] if row.get("id") != session.id]
        rows.append(asdict(session))
        self._data["deposit_sessions"] = rows
        self._save()
        return session

    def list_deposit_sessions(self, fascicolo_id: str) -> list[DepositSession]:
        rows = [
            dataclass_from_dict(DepositSession, row)
            for row in self._data["deposit_sessions"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
        return sorted(rows, key=lambda item: item.created_at, reverse=True)

    def add_receipt(self, receipt: DepositReceipt) -> DepositReceipt:
        self._data["deposit_receipts"].append(asdict(receipt))
        self.add_timeline_event(
            receipt.deposit_session_id,
            receipt.fascicolo_id,
            receipt.receipt_type,
            receipt.status,
            receipt.message or "Ricevuta importata e collegata al deposito.",
            evidence_ref=receipt.id,
        )
        self._save()
        return receipt

    def list_receipts(self, deposito_id: str) -> list[DepositReceipt]:
        return [
            dataclass_from_dict(DepositReceipt, row)
            for row in self._data["deposit_receipts"]
            if row.get("deposit_session_id") == deposito_id
        ]

    def add_timeline_event(self, deposito_id: str, fascicolo_id: str, event_type: str, status: str, message: str, *, evidence_ref: str = "") -> TimelineEvent:
        event = TimelineEvent(new_id("evt"), deposito_id, fascicolo_id, event_type, status, message, evidence_ref=evidence_ref)
        self._data["deposit_timeline_events"].append(asdict(event))
        self._save()
        return event

    def list_timeline(self, deposito_id: str) -> list[TimelineEvent]:
        rows = [
            dataclass_from_dict(TimelineEvent, row)
            for row in self._data["deposit_timeline_events"]
            if row.get("deposit_session_id") == deposito_id
        ]
        return sorted(rows, key=lambda item: item.created_at)

    def save_evidence_pack(self, pack: EvidencePack) -> EvidencePack:
        rows = [row for row in self._data["evidence_packs"] if row.get("id") != pack.id]
        rows.append(asdict(pack))
        self._data["evidence_packs"] = rows
        self._save()
        return pack

    def get_evidence_pack(self, deposito_id: str) -> EvidencePack | None:
        for row in reversed(self._data["evidence_packs"]):
            if row.get("deposit_session_id") == deposito_id:
                return dataclass_from_dict(EvidencePack, row)
        return None

    def audit(self, fascicolo_id: str, event_type: str, *, actor: str = "", message: str = "", reason: str = "", payload: dict[str, Any] | None = None) -> AuditEvent:
        event = AuditEvent(new_id("audit"), fascicolo_id, event_type, actor=actor, message=message, reason=reason, payload=payload or {})
        self._data["audit_events"].append(asdict(event))
        self._save()
        return event

    def list_audit(self, fascicolo_id: str) -> list[AuditEvent]:
        return [
            dataclass_from_dict(AuditEvent, row)
            for row in self._data["audit_events"]
            if row.get("fascicolo_id") == fascicolo_id
        ]
