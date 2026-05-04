"""Modelli deterministici per la Regia Operativa Fascicolo.

Il modulo non decide con AI: descrive stati, profili, slot, controlli,
ricevute ed evidence pack in strutture serializzabili e auditabili.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class PracticeState(str, Enum):
    PRE_FASCICOLO = "PRE_FASCICOLO"
    IN_ATTESA_PREVENTIVO = "IN_ATTESA_PREVENTIVO"
    PREVENTIVO_INVIATO = "PREVENTIVO_INVIATO"
    PREVENTIVO_ACCETTATO = "PREVENTIVO_ACCETTATO"
    INCARICO_DA_FIRMARE = "INCARICO_DA_FIRMARE"
    IN_ATTESA_ACCONTO = "IN_ATTESA_ACCONTO"
    PRONTO_APERTURA_FASCICOLO = "PRONTO_APERTURA_FASCICOLO"
    FASCICOLO_APERTO = "FASCICOLO_APERTO"
    DOCUMENTI_DA_COMPLETARE = "DOCUMENTI_DA_COMPLETARE"
    ATTO_DA_REDIGERE = "ATTO_DA_REDIGERE"
    ATTO_DA_FIRMARE = "ATTO_DA_FIRMARE"
    VALIDAZIONE_IN_CORSO = "VALIDAZIONE_IN_CORSO"
    BLOCCATO_DA_ERRORI = "BLOCCATO_DA_ERRORI"
    PRONTO_AL_DEPOSITO = "PRONTO_AL_DEPOSITO"
    DEPOSITO_IN_PREPARAZIONE = "DEPOSITO_IN_PREPARAZIONE"
    DEPOSITO_INVIATO = "DEPOSITO_INVIATO"
    IN_ATTESA_RICEVUTE = "IN_ATTESA_RICEVUTE"
    ACCETTATO_PEC = "ACCETTATO_PEC"
    CONSEGNATO = "CONSEGNATO"
    IN_ATTESA_CONTROLLI = "IN_ATTESA_CONTROLLI"
    CONTROLLI_OK = "CONTROLLI_OK"
    CONTROLLI_WARNING = "CONTROLLI_WARNING"
    CONTROLLI_ERRORE = "CONTROLLI_ERRORE"
    IN_ATTESA_CANCELLERIA = "IN_ATTESA_CANCELLERIA"
    ACCETTATO_DA_CANCELLERIA = "ACCETTATO_DA_CANCELLERIA"
    RIFIUTATO_DA_CANCELLERIA = "RIFIUTATO_DA_CANCELLERIA"
    ACQUISITO = "ACQUISITO"
    DA_CORREGGERE = "DA_CORREGGERE"
    FASE_SUCCESSIVA = "FASE_SUCCESSIVA"
    DEFINITO = "DEFINITO"
    ARCHIVIATO = "ARCHIVIATO"


class SlotStatus(str, Enum):
    MANCANTE = "MANCANTE"
    PRESENTE = "PRESENTE"
    DA_VALIDARE = "DA_VALIDARE"
    VALIDO = "VALIDO"
    WARNING = "WARNING"
    NON_VALIDO = "NON_VALIDO"
    NON_APPLICABILE = "NON_APPLICABILE"


class SlotType(str, Enum):
    ATTO_PRINCIPALE = "ATTO_PRINCIPALE"
    PROCURA = "PROCURA"
    CONTRIBUTO_UNIFICATO = "CONTRIBUTO_UNIFICATO"
    MARCA_BOLLO = "MARCA_BOLLO"
    NOTA_ISCRIZIONE_RUOLO = "NOTA_ISCRIZIONE_RUOLO"
    DOCUMENTO_PROVA = "DOCUMENTO_PROVA"
    DOCUMENTO_CLIENTE = "DOCUMENTO_CLIENTE"
    DOCUMENTO_CONTROPARTE = "DOCUMENTO_CONTROPARTE"
    COMUNICAZIONE = "COMUNICAZIONE"
    RICEVUTA = "RICEVUTA"
    ESITO_PORTALE = "ESITO_PORTALE"
    PROVVEDIMENTO = "PROVVEDIMENTO"
    ALLEGATO = "ALLEGATO"
    ALTRO = "ALTRO"


class ValidatorStatus(str, Enum):
    OK = "OK"
    WARNING = "WARNING"
    BLOCK = "BLOCK"
    PENDING = "PENDING"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    ERROR = "ERROR"


class DepositStatus(str, Enum):
    NON_INVIATO = "NON_INVIATO"
    IN_PREPARAZIONE = "IN_PREPARAZIONE"
    PRONTO = "PRONTO"
    INVIATO = "INVIATO"
    ACCETTATO_PEC = "ACCETTATO_PEC"
    CONSEGNATO = "CONSEGNATO"
    CONTROLLI_OK = "CONTROLLI_OK"
    CONTROLLI_WARNING = "CONTROLLI_WARNING"
    CONTROLLI_ERRORE = "CONTROLLI_ERRORE"
    ACCETTATO_CANCELLERIA = "ACCETTATO_CANCELLERIA"
    RIFIUTATO_CANCELLERIA = "RIFIUTATO_CANCELLERIA"
    ACQUISITO = "ACQUISITO"
    DA_CORREGGERE = "DA_CORREGGERE"
    ERRORE = "ERRORE"


class ReceiptType(str, Enum):
    ACCETTAZIONE_PEC = "ACCETTAZIONE_PEC"
    CONSEGNA_PEC = "CONSEGNA_PEC"
    CONTROLLI_AUTOMATICI = "CONTROLLI_AUTOMATICI"
    ESITO_CANCELLERIA = "ESITO_CANCELLERIA"
    ESITO_PDP = "ESITO_PDP"
    ESITO_PAT = "ESITO_PAT"
    ESITO_PTT = "ESITO_PTT"
    ESITO_SIGP = "ESITO_SIGP"
    ESITO_PORTALE = "ESITO_PORTALE"
    ALTRO = "ALTRO"


@dataclass
class PracticeRequirement:
    key: str
    label: str
    required: bool = True
    blocking: bool = True
    source: str = "catalogo_operativo"
    message: str = ""
    suggested_action: str = ""


@dataclass
class ChecklistItem:
    id: str
    fascicolo_id: str
    profile_id: str
    key: str
    label: str
    required: bool = True
    blocking: bool = True
    status: str = "DA_COMPLETARE"
    message: str = ""
    suggested_action: str = ""
    sort_order: int = 0
    source: str = "catalogo_operativo"


@dataclass
class DocumentSlot:
    id: str
    fascicolo_id: str
    profile_id: str
    slot_key: str
    label: str
    type: str
    required: bool = True
    blocking: bool = True
    document_id: str = ""
    status: str = SlotStatus.MANCANTE.value
    validators: list[str] = field(default_factory=list)
    last_validation_at: str = ""
    message: str = ""
    suggested_action: str = ""
    sort_order: int = 0


@dataclass
class ValidationResult:
    key: str
    status: str
    severity: str
    message: str
    technical_detail: str = ""
    suggested_action: str = ""
    source: str = "practice_engine"
    evidence: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    @property
    def blocking(self) -> bool:
        return self.status in {ValidatorStatus.BLOCK.value, ValidatorStatus.ERROR.value}


@dataclass
class PracticeProfile:
    id: str
    code: str
    name: str
    area: str
    fascicolo_type: str
    channel: str
    registry: str
    workflow_code: str
    practice_id: str
    procedure_code: str
    version: str = "1.0"
    source: str = "legal_platform_catalog"
    active: bool = True
    required_documents: list[PracticeRequirement] = field(default_factory=list)
    checklist_items: list[PracticeRequirement] = field(default_factory=list)
    deadlines: list[dict[str, Any]] = field(default_factory=list)
    template_labels: list[str] = field(default_factory=list)
    required_slots: list[dict[str, Any]] = field(default_factory=list)
    blocking_validators: list[str] = field(default_factory=list)
    warning_validators: list[str] = field(default_factory=list)
    depositable: bool = False
    requires_human_review: bool = True
    requires_hearing: bool = False
    requires_registry_enrollment: bool = False
    allows_settlement: bool = True
    requires_registry_enrollment_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["required_documents"] = [asdict(item) for item in self.required_documents]
        data["checklist_items"] = [asdict(item) for item in self.checklist_items]
        return data


@dataclass
class ResolverResult:
    profile: PracticeProfile | None
    confidence: float
    reason: str
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    needs_manual_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile.to_dict() if self.profile else None,
            "confidence": round(float(self.confidence), 2),
            "reason": self.reason,
            "alternatives": list(self.alternatives),
            "needs_manual_confirmation": bool(self.needs_manual_confirmation),
        }


@dataclass
class DepositSession:
    id: str
    fascicolo_id: str
    profile_id: str
    channel: str
    status: str = DepositStatus.NON_INVIATO.value
    transport_mode: str = "non_configurato"
    simulated: bool = False
    real_transport: bool = False
    predeposit_status: str = "NON_ESEGUITO"
    messages: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    sent_at: str = ""
    acquired_at: str = ""
    final_receipt_id: str = ""


@dataclass
class DepositReceipt:
    id: str
    deposit_session_id: str
    fascicolo_id: str
    receipt_type: str
    status: str
    positive: bool = False
    source: str = "import_guidato"
    original_name: str = ""
    original_hash_sha256: str = ""
    original_path: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    imported_at: str = field(default_factory=utc_now)
    message: str = ""


@dataclass
class TimelineEvent:
    id: str
    deposit_session_id: str
    fascicolo_id: str
    event_type: str
    status: str
    message: str
    created_at: str = field(default_factory=utc_now)
    evidence_ref: str = ""


@dataclass
class EvidencePack:
    id: str
    fascicolo_id: str
    deposit_session_id: str
    path: str
    hash_sha256: str
    created_at: str = field(default_factory=utc_now)
    available: bool = True


@dataclass
class AuditEvent:
    id: str
    fascicolo_id: str
    event_type: str
    actor: str = ""
    message: str = ""
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)


def dataclass_from_dict(cls: type[Any], payload: dict[str, Any]) -> Any:
    fields = getattr(cls, "__dataclass_fields__", {})
    values = {key: payload.get(key) for key in fields if key in payload}
    return cls(**values)
