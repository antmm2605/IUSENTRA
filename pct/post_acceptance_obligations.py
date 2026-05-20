"""Valutazione conservativa degli adempimenti successivi all'accettazione."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pct.evidence_vault import assert_required_evidence
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


class ObligationType(str, Enum):
    NOTIFICA = "NOTIFICA"
    RELATA = "RELATA"
    PROOF_COLLECTION = "ALTRO"
    DEPOSITO_PROVA_NOTIFICA = "DEPOSITO_PROVA_NOTIFICA"
    MONITORAGGIO_PROVVEDIMENTO = "MONITORAGGIO_PROVVEDIMENTO"


class ObligationStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


OBLIGATION_TYPES: tuple[str, ...] = tuple(item.value for item in ObligationType)
OBLIGATION_STATUSES: tuple[str, ...] = tuple(status.value for status in ObligationStatus)


def _prefix(xsd_code: str | None) -> str:
    return str(xsd_code or "")[:3]


def _obligation(
    obligation_type: str,
    *,
    evidence_required: list[str] | None = None,
    legal_basis: str = "",
    notes: str = "",
) -> dict[str, Any]:
    return {
        "obligation_type": obligation_type,
        "evidence_required_json": evidence_required or [],
        "legal_basis": legal_basis,
        "human_review_required": 1,
        "notes": notes,
    }


def evaluate_post_acceptance_obligations(
    repo: ProcedureLifecycleRepository,
    *,
    fascicolo_id: str,
    procedure_code: str,
    xsd_code: str | None,
    trigger_event: str,
    proof_deposit_configured: bool = True,
) -> list[int]:
    prefix = _prefix(xsd_code)
    planned: list[dict[str, Any]]
    if prefix in {"010", "050"}:
        planned = [
            _obligation(ObligationType.NOTIFICA.value, evidence_required=["NOTIFICATION_RECEIPT"], notes="Notifica decreto e ricorso da valutare dopo provvedimento."),
            _obligation(ObligationType.RELATA.value, evidence_required=["NOTIFICATION_RELATA"], notes="Relata da associare alla notifica."),
            _obligation(ObligationType.PROOF_COLLECTION.value, evidence_required=["PROOF_OF_DELIVERY"], notes="PROOF_COLLECTION: raccolta prova notifica obbligatoria in review."),
        ]
        if proof_deposit_configured:
            planned.append(
                _obligation(ObligationType.DEPOSITO_PROVA_NOTIFICA.value, evidence_required=["DEPOSIT_RECEIPT"], notes="Deposito prova notifica se previsto dal caso.")
            )
    elif prefix == "030":
        planned = [
            _obligation(ObligationType.NOTIFICA.value, evidence_required=["NOTIFICATION_RECEIPT"], notes="Decisione notifica anticipata per sfratto/convalida."),
            _obligation(ObligationType.RELATA.value, evidence_required=["NOTIFICATION_RELATA"], notes="Relata da predisporre e verificare."),
        ]
    elif prefix in {"011", "012", "014", "015", "017", "019", "051", "052", "053", "055", "059"}:
        planned = [
            _obligation(ObligationType.MONITORAGGIO_PROVVEDIMENTO.value, notes="Notifica o post-notifica condizionale: review obbligatoria."),
            _obligation(ObligationType.NOTIFICA.value, evidence_required=["NOTIFICATION_RECEIPT"], notes="Obbligo condizionale da confermare."),
        ]
    elif prefix == "020":
        planned = [
            _obligation(ObligationType.MONITORAGGIO_PROVVEDIMENTO.value, notes="Udienza e notifica condizionali per possessoria."),
            _obligation(ObligationType.NOTIFICA.value, evidence_required=["NOTIFICATION_RECEIPT"], notes="Obbligo condizionale da confermare."),
        ]
    else:
        planned = [
            _obligation(ObligationType.MONITORAGGIO_PROVVEDIMENTO.value, notes="Caso non codificato: review post-accettazione obbligatoria."),
            _obligation(ObligationType.PROOF_COLLECTION.value, notes="POST_ACCEPTANCE_REVIEW: valutazione avvocato richiesta prima di concludere il workflow."),
        ]

    ids: list[int] = []
    for item in planned:
        ids.append(
            repo.add_obligation(
                {
                    "fascicolo_id": fascicolo_id,
                    "procedure_code": procedure_code,
                    "xsd_code": xsd_code,
                    "trigger_event": trigger_event,
                    "obligation_type": item["obligation_type"],
                    "legal_basis": item.get("legal_basis"),
                    "required_documents_json": [],
                    "evidence_required_json": item.get("evidence_required_json", []),
                    "human_review_required": item.get("human_review_required", 1),
                    "notes": item.get("notes"),
                }
            )
        )
    return ids


def complete_obligation(repo: ProcedureLifecycleRepository, obligation_id: int) -> None:
    with repo.connect() as conn:
        obligation = repo._fetch_one(conn, "SELECT * FROM post_acceptance_obligations WHERE id = ?", (obligation_id,))
    if not obligation:
        raise ValueError("Obbligo non trovato.")
    required = repo.list_obligations(str(obligation.get("fascicolo_id") or ""))
    current = next((row for row in required if int(row.get("id") or 0) == obligation_id), {})
    evidence_required = list(current.get("evidence_required_json") or [])
    if evidence_required:
        assert_required_evidence(repo, str(obligation.get("fascicolo_id") or ""), evidence_required)
    repo.update_obligation(
        obligation_id,
        {
            "obligation_status": ObligationStatus.COMPLETED.value,
            "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        },
    )
