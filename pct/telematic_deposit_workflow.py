"""Workflow deposito telematico governato da stati, ricevute ed evidenze."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pct.digital_signature_workflow import is_signature_required
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


class DepositStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    SENT = "SENT"
    PEC_ACCEPTED = "PEC_ACCEPTED"
    PEC_DELIVERED = "PEC_DELIVERED"
    CONTROLS_RECEIVED = "CONTROLS_RECEIVED"
    OFFICE_ACCEPTED = "OFFICE_ACCEPTED"
    OFFICE_REJECTED = "OFFICE_REJECTED"
    TECHNICAL_ERROR = "TECHNICAL_ERROR"
    CANCELLED = "CANCELLED"


class DepositReceiptType(str, Enum):
    PEC_ACCETTAZIONE = "PEC_ACCETTAZIONE"
    PEC_CONSEGNA = "PEC_CONSEGNA"
    ESITO_CONTROLLI = "ESITO_CONTROLLI"
    ACCETTAZIONE_DEPOSITO = "ACCETTAZIONE_DEPOSITO"
    RIFIUTO_DEPOSITO = "RIFIUTO_DEPOSITO"
    ERRORE_TECNICO = "ERRORE_TECNICO"
    ALTRO = "ALTRO"


DEPOSIT_STATUSES: tuple[str, ...] = tuple(status.value for status in DepositStatus)
DEPOSIT_RECEIPT_TYPES: tuple[str, ...] = tuple(receipt.value for receipt in DepositReceiptType)

RECEIPT_STATUS_BY_TYPE = {
    DepositReceiptType.PEC_ACCETTAZIONE.value: DepositStatus.PEC_ACCEPTED.value,
    DepositReceiptType.PEC_CONSEGNA.value: DepositStatus.PEC_DELIVERED.value,
    DepositReceiptType.ESITO_CONTROLLI.value: DepositStatus.CONTROLS_RECEIVED.value,
    DepositReceiptType.ACCETTAZIONE_DEPOSITO.value: DepositStatus.OFFICE_ACCEPTED.value,
    DepositReceiptType.RIFIUTO_DEPOSITO.value: DepositStatus.OFFICE_REJECTED.value,
    DepositReceiptType.ERRORE_TECNICO.value: DepositStatus.TECHNICAL_ERROR.value,
}


class RealDepositConnector:
    """Interfaccia futura: nessun invio reale è implementato in questa fase."""

    def send(self, package: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("Deposito reale non configurato: usare un connettore autorizzato o lo stub di test.")


class StubDepositConnector:
    """Stub deterministico per test e sviluppo locale."""

    def send(self, package: dict[str, Any]) -> dict[str, Any]:
        return {"mode": "stub", "package_id": package.get("id"), "sent": True}


def _active_xsd(repo: ProcedureLifecycleRepository, xsd_code: str | None) -> bool:
    if not xsd_code:
        return False
    row = repo.get_xsd_object(str(xsd_code))
    return bool(row and int(row.get("active") or 0) == 1)


def create_deposit_package(
    repo: ProcedureLifecycleRepository,
    *,
    fascicolo_id: str,
    procedure_code: str,
    xsd_code: str,
    channel_code: str = "PCT_CIVILE",
    **payload: Any,
) -> int:
    if not _active_xsd(repo, xsd_code):
        raise ValueError("Il pacchetto richiede un xsd_code attivo nel catalogo ministeriale importato.")
    return repo.create_deposit_package(
        {
            "fascicolo_id": fascicolo_id,
            "procedure_code": procedure_code,
            "xsd_code": xsd_code,
            "channel_code": channel_code,
            "office_code": payload.get("office_code"),
            "registry_code": payload.get("registry_code"),
            "dati_atto_xml_id": payload.get("dati_atto_xml_id"),
            "envelope_file_id": payload.get("envelope_file_id"),
            "deposit_mode": payload.get("deposit_mode", "stub"),
            "package_hash": payload.get("package_hash"),
            "notes": payload.get("notes"),
        }
    )


def validate_package_ready(repo: ProcedureLifecycleRepository, package_id: int) -> dict[str, Any]:
    package = repo.get_deposit_package(package_id)
    if not package:
        raise ValueError("Pacchetto deposito non trovato.")
    errors: list[str] = []
    if not package.get("xsd_code"):
        errors.append("xsd_code mancante.")
    elif not _active_xsd(repo, str(package.get("xsd_code"))):
        errors.append("xsd_code non attivo nel catalogo ministeriale.")
    if not package.get("dati_atto_xml_id"):
        errors.append("DatiAtto.xml non associato.")
    if not package.get("envelope_file_id"):
        errors.append("Busta o pacchetto deposito non associato.")
    signature_needed = is_signature_required(
        str(package.get("procedure_code") or ""),
        str(package.get("xsd_code") or ""),
        "deposit_package",
    )
    signatures = repo.list_signature_events(str(package.get("fascicolo_id") or ""))
    if signature_needed and not any(row.get("verification_status") == "VERIFIED" for row in signatures if int(row.get("required") or 0) == 1):
        errors.append("Firma digitale richiesta ma non verificata.")
    ready = not errors
    if ready and package.get("deposit_status") == DepositStatus.DRAFT.value:
        repo.update_deposit_package(package_id, {"deposit_status": DepositStatus.READY.value})
    return {"ready": ready, "errors": errors}


def mark_deposit_sent(
    repo: ProcedureLifecycleRepository,
    package_id: int,
    connector: StubDepositConnector | RealDepositConnector | None = None,
) -> dict[str, Any]:
    package = repo.get_deposit_package(package_id)
    if not package:
        raise ValueError("Pacchetto deposito non trovato.")
    if package.get("deposit_status") != DepositStatus.READY.value:
        raise ValueError("Il deposito può essere inviato solo dopo stato READY.")
    active_connector = connector or StubDepositConnector()
    result = active_connector.send(package)
    repo.update_deposit_package(
        package_id,
        {
            "deposit_status": DepositStatus.SENT.value,
            "sent_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "deposit_mode": result.get("mode", "stub"),
        },
    )
    return result


def add_deposit_receipt(repo: ProcedureLifecycleRepository, package_id: int, receipt_type: str, **payload: Any) -> int:
    if receipt_type not in DEPOSIT_RECEIPT_TYPES:
        raise ValueError("receipt_type non ammesso.")
    receipt_id = repo.add_deposit_receipt(
        {
            "deposit_package_id": package_id,
            "receipt_type": receipt_type,
            "receipt_status": payload.get("receipt_status", "RECEIVED"),
            "pec_message_id": payload.get("pec_message_id"),
            "pec_subject": payload.get("pec_subject"),
            "sender": payload.get("sender"),
            "recipient": payload.get("recipient"),
            "received_at": payload.get("received_at") or datetime.now(UTC).isoformat(timespec="seconds"),
            "event_time": payload.get("event_time"),
            "document_id": payload.get("document_id"),
            "parsed_payload_json": payload.get("parsed_payload_json", {}),
            "notes": payload.get("notes"),
        }
    )
    update_deposit_status_from_receipts(repo, package_id)
    return receipt_id


def assert_office_acceptance_evidence(repo: ProcedureLifecycleRepository, package_id: int) -> None:
    receipts = repo.list_deposit_receipts(package_id)
    if not any(row.get("receipt_type") == DepositReceiptType.ACCETTAZIONE_DEPOSITO.value for row in receipts):
        raise ValueError("OFFICE_ACCEPTED richiede ricevuta ACCETTAZIONE_DEPOSITO o equivalente validato.")


def update_deposit_status_from_receipts(repo: ProcedureLifecycleRepository, package_id: int) -> str:
    receipts = repo.list_deposit_receipts(package_id)
    status = str((repo.get_deposit_package(package_id) or {}).get("deposit_status") or DepositStatus.DRAFT.value)
    for receipt_type in (
        DepositReceiptType.PEC_ACCETTAZIONE.value,
        DepositReceiptType.PEC_CONSEGNA.value,
        DepositReceiptType.ESITO_CONTROLLI.value,
        DepositReceiptType.ACCETTAZIONE_DEPOSITO.value,
        DepositReceiptType.RIFIUTO_DEPOSITO.value,
        DepositReceiptType.ERRORE_TECNICO.value,
    ):
        if any(row.get("receipt_type") == receipt_type for row in receipts):
            status = RECEIPT_STATUS_BY_TYPE[receipt_type]
    updates: dict[str, Any] = {"deposit_status": status}
    if status == DepositStatus.OFFICE_ACCEPTED.value:
        assert_office_acceptance_evidence(repo, package_id)
        updates["accepted_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    if status in {DepositStatus.OFFICE_REJECTED.value, DepositStatus.TECHNICAL_ERROR.value}:
        updates["rejected_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        rejecting = next(
            (
                row
                for row in receipts
                if row.get("receipt_type")
                in {DepositReceiptType.RIFIUTO_DEPOSITO.value, DepositReceiptType.ERRORE_TECNICO.value}
            ),
            {},
        )
        updates["rejection_reason"] = rejecting.get("notes")
    repo.update_deposit_package(package_id, updates)
    return status
