"""State machine e template lifecycle per pratiche telematiche/procedurali."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository
from pct.procedure_xsd_mapper import CAUTELARI_PREFIXES, infer_mapping_for_xsd


class WorkflowState(str, Enum):
    PRATICA_APERTA = "PRATICA_APERTA"
    PROCEDURA_CLASSIFICATA = "PROCEDURA_CLASSIFICATA"
    DOCUMENTI_RICHIESTI = "DOCUMENTI_RICHIESTI"
    DOCUMENTI_COMPLETI = "DOCUMENTI_COMPLETI"
    ATTO_GENERATO = "ATTO_GENERATO"
    REVISIONE_AVVOCATO = "REVISIONE_AVVOCATO"
    PRONTO_PER_FIRMA = "PRONTO_PER_FIRMA"
    FIRMA_RICHIESTA = "FIRMA_RICHIESTA"
    FIRMATO = "FIRMATO"
    BUSTA_GENERATA = "BUSTA_GENERATA"
    DEPOSITO_PRONTO = "DEPOSITO_PRONTO"
    DEPOSITO_INVIATO = "DEPOSITO_INVIATO"
    PEC_ACCETTAZIONE_RICEVUTA = "PEC_ACCETTAZIONE_RICEVUTA"
    PEC_CONSEGNA_RICEVUTA = "PEC_CONSEGNA_RICEVUTA"
    ESITO_CONTROLLI_RICEVUTO = "ESITO_CONTROLLI_RICEVUTO"
    DEPOSITO_ACCETTATO = "DEPOSITO_ACCETTATO"
    DEPOSITO_RIFIUTATO = "DEPOSITO_RIFIUTATO"
    PROVVEDIMENTO_ATTESO = "PROVVEDIMENTO_ATTESO"
    ADEMPIMENTO_SUCCESSIVO_DA_VALUTARE = "ADEMPIMENTO_SUCCESSIVO_DA_VALUTARE"
    NOTIFICA_DA_EFFETTUARE = "NOTIFICA_DA_EFFETTUARE"
    RELATA_DA_GENERARE = "RELATA_DA_GENERARE"
    NOTIFICA_EFFETTUATA = "NOTIFICA_EFFETTUATA"
    PROVA_NOTIFICA_ACQUISITA = "PROVA_NOTIFICA_ACQUISITA"
    PROVA_NOTIFICA_DA_DEPOSITARE = "PROVA_NOTIFICA_DA_DEPOSITARE"
    PROVA_NOTIFICA_DEPOSITATA = "PROVA_NOTIFICA_DEPOSITATA"
    MONITORAGGIO_FASCICOLO = "MONITORAGGIO_FASCICOLO"
    CHIUSA = "CHIUSA"


class LifecycleStepType(str, Enum):
    CLASSIFICATION = "CLASSIFICATION"
    DOCUMENT_COLLECTION = "DOCUMENT_COLLECTION"
    ACT_DRAFT = "ACT_DRAFT"
    LEGAL_REVIEW = "LEGAL_REVIEW"
    SIGNATURE_DECISION = "SIGNATURE_DECISION"
    SIGNATURE = "SIGNATURE"
    PACKAGE_BUILD = "PACKAGE_BUILD"
    PACKAGE_VALIDATE = "PACKAGE_VALIDATE"
    DEPOSIT_SEND = "DEPOSIT_SEND"
    RECEIPT_WAIT = "RECEIPT_WAIT"
    ACCEPTANCE_CHECK = "ACCEPTANCE_CHECK"
    POST_ACCEPTANCE_REVIEW = "POST_ACCEPTANCE_REVIEW"
    NOTIFICATION_DECISION = "NOTIFICATION_DECISION"
    NOTIFICATION = "NOTIFICATION"
    RELATA = "RELATA"
    PROOF_COLLECTION = "PROOF_COLLECTION"
    PROOF_DEPOSIT = "PROOF_DEPOSIT"
    MONITORING = "MONITORING"
    CLOSURE = "CLOSURE"


WORKFLOW_STATES: tuple[str, ...] = tuple(state.value for state in WorkflowState)
LIFECYCLE_STEP_TYPES: tuple[str, ...] = tuple(step.value for step in LifecycleStepType)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "PRATICA_APERTA": {"PROCEDURA_CLASSIFICATA", "DOCUMENTI_RICHIESTI"},
    "PROCEDURA_CLASSIFICATA": {"DOCUMENTI_RICHIESTI"},
    "DOCUMENTI_RICHIESTI": {"DOCUMENTI_COMPLETI"},
    "DOCUMENTI_COMPLETI": {"ATTO_GENERATO"},
    "ATTO_GENERATO": {"REVISIONE_AVVOCATO"},
    "REVISIONE_AVVOCATO": {"PRONTO_PER_FIRMA", "DOCUMENTI_COMPLETI"},
    "PRONTO_PER_FIRMA": {"FIRMA_RICHIESTA", "FIRMATO"},
    "FIRMA_RICHIESTA": {"FIRMATO"},
    "FIRMATO": {"BUSTA_GENERATA"},
    "BUSTA_GENERATA": {"DEPOSITO_PRONTO"},
    "DEPOSITO_PRONTO": {"DEPOSITO_INVIATO"},
    "DEPOSITO_INVIATO": {"PEC_ACCETTAZIONE_RICEVUTA", "DEPOSITO_RIFIUTATO"},
    "PEC_ACCETTAZIONE_RICEVUTA": {"PEC_CONSEGNA_RICEVUTA"},
    "PEC_CONSEGNA_RICEVUTA": {"ESITO_CONTROLLI_RICEVUTO"},
    "ESITO_CONTROLLI_RICEVUTO": {"DEPOSITO_ACCETTATO", "DEPOSITO_RIFIUTATO"},
    "DEPOSITO_ACCETTATO": {"PROVVEDIMENTO_ATTESO", "ADEMPIMENTO_SUCCESSIVO_DA_VALUTARE", "MONITORAGGIO_FASCICOLO"},
    "DEPOSITO_RIFIUTATO": {"DOCUMENTI_COMPLETI", "CHIUSA"},
    "PROVVEDIMENTO_ATTESO": {"ADEMPIMENTO_SUCCESSIVO_DA_VALUTARE"},
    "ADEMPIMENTO_SUCCESSIVO_DA_VALUTARE": {"NOTIFICA_DA_EFFETTUARE", "MONITORAGGIO_FASCICOLO"},
    "NOTIFICA_DA_EFFETTUARE": {"RELATA_DA_GENERARE", "NOTIFICA_EFFETTUATA"},
    "RELATA_DA_GENERARE": {"NOTIFICA_EFFETTUATA"},
    "NOTIFICA_EFFETTUATA": {"PROVA_NOTIFICA_ACQUISITA"},
    "PROVA_NOTIFICA_ACQUISITA": {"PROVA_NOTIFICA_DA_DEPOSITARE", "MONITORAGGIO_FASCICOLO"},
    "PROVA_NOTIFICA_DA_DEPOSITARE": {"PROVA_NOTIFICA_DEPOSITATA"},
    "PROVA_NOTIFICA_DEPOSITATA": {"MONITORAGGIO_FASCICOLO"},
    "MONITORAGGIO_FASCICOLO": {"CHIUSA"},
}

STATE_TO_INSTANCE_STATUS = {
    "PRATICA_APERTA": "OPEN",
    "DEPOSITO_INVIATO": "WAITING_RECEIPT",
    "PEC_ACCETTAZIONE_RICEVUTA": "WAITING_OFFICE_ACCEPTANCE",
    "PEC_CONSEGNA_RICEVUTA": "WAITING_OFFICE_ACCEPTANCE",
    "ESITO_CONTROLLI_RICEVUTO": "WAITING_OFFICE_ACCEPTANCE",
    "NOTIFICA_DA_EFFETTUARE": "WAITING_NOTIFICATION",
    "PROVA_NOTIFICA_DA_DEPOSITARE": "WAITING_PROOF_DEPOSIT",
    "CHIUSA": "COMPLETED",
}

STEP_LABELS = {
    "CLASSIFICATION": "Classificazione procedura",
    "DOCUMENT_COLLECTION": "Raccolta documenti",
    "ACT_DRAFT": "Redazione atto",
    "LEGAL_REVIEW": "Revisione avvocato",
    "SIGNATURE_DECISION": "Decisione firma digitale",
    "SIGNATURE": "Firma digitale",
    "PACKAGE_BUILD": "Generazione busta",
    "PACKAGE_VALIDATE": "Validazione pacchetto",
    "DEPOSIT_SEND": "Invio deposito",
    "RECEIPT_WAIT": "Acquisizione ricevute",
    "ACCEPTANCE_CHECK": "Verifica accettazione",
    "POST_ACCEPTANCE_REVIEW": "Valutazione adempimenti successivi",
    "NOTIFICATION_DECISION": "Decisione notifica",
    "NOTIFICATION": "Notifica",
    "RELATA": "Relata",
    "PROOF_COLLECTION": "Acquisizione prova",
    "PROOF_DEPOSIT": "Deposito prova notifica",
    "MONITORING": "Monitoraggio fascicolo",
    "CLOSURE": "Chiusura",
}


@dataclass(frozen=True)
class LifecycleTemplateReport:
    dry_run: bool
    xsd_total: int
    templates_generated: int
    needs_review: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _prefix(xsd_code: str | None) -> str:
    return str(xsd_code or "")[:3]


def _workflow_status_for_state(state: str) -> str:
    return STATE_TO_INSTANCE_STATUS.get(state, "IN_PROGRESS")


def _assert_transition_allowed(current: str, target: str) -> None:
    if target not in WORKFLOW_STATES:
        raise ValueError(f"Stato workflow non ammesso: {target}")
    if current and target not in ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Transizione non consentita: {current} -> {target}")


def _signature_required_for_instance(repo: ProcedureLifecycleRepository, instance: dict[str, Any]) -> bool:
    fascicolo_id = str(instance.get("fascicolo_id") or "")
    if _prefix(instance.get("xsd_code")) in {"010", "011", "012", "014", "015", "017", "019", "020", "030", "050", "051", "052", "053", "055", "059"}:
        return True
    return any(int(row.get("required") or 0) == 1 for row in repo.list_signature_events(fascicolo_id))


def _has_verified_signature(repo: ProcedureLifecycleRepository, fascicolo_id: str) -> bool:
    return any(
        row.get("verification_status") == "VERIFIED"
        for row in repo.list_signature_events(fascicolo_id)
        if int(row.get("required") or 0) == 1
    )


def _has_office_acceptance(repo: ProcedureLifecycleRepository, fascicolo_id: str) -> bool:
    with repo.connect() as conn:
        packages = repo._fetch_all(conn, "SELECT * FROM telematic_deposit_packages WHERE fascicolo_id = ?", (fascicolo_id,))
    for package in packages:
        if package.get("deposit_status") == "OFFICE_ACCEPTED":
            return True
        receipts = repo.list_deposit_receipts(int(package["id"]))
        if any(row.get("receipt_type") == "ACCETTAZIONE_DEPOSITO" for row in receipts):
            return True
    return False


def _has_notification_sent(repo: ProcedureLifecycleRepository, fascicolo_id: str) -> bool:
    with repo.connect() as conn:
        rows = repo._fetch_all(conn, "SELECT * FROM notification_events WHERE fascicolo_id = ?", (fascicolo_id,))
    return any(row.get("status") in {"SENT", "DELIVERED", "PROOF_ACQUIRED", "PROOF_DEPOSIT_REQUIRED", "PROOF_DEPOSITED"} for row in rows)


def _has_notification_proof(repo: ProcedureLifecycleRepository, fascicolo_id: str) -> bool:
    return bool(repo.list_evidence_documents(fascicolo_id, evidence_types=("NOTIFICATION_RECEIPT", "PROOF_OF_DELIVERY")))


def _has_pending_obligations(repo: ProcedureLifecycleRepository, fascicolo_id: str) -> bool:
    return bool(repo.list_obligations(fascicolo_id, statuses=("PENDING",)))


def _assert_severe_rules(repo: ProcedureLifecycleRepository, instance: dict[str, Any], target_state: str) -> None:
    fascicolo_id = str(instance.get("fascicolo_id") or "")
    if target_state == "FIRMATO" and _signature_required_for_instance(repo, instance) and not _has_verified_signature(repo, fascicolo_id):
        raise ValueError("FIRMATO richiede digital_signature_events con verifica VERIFIED quando la firma è richiesta.")
    if target_state == "DEPOSITO_ACCETTATO" and not _has_office_acceptance(repo, fascicolo_id):
        raise ValueError("DEPOSITO_ACCETTATO richiede ricevuta ACCETTAZIONE_DEPOSITO o equivalente validato.")
    if target_state == "NOTIFICA_EFFETTUATA" and not _has_notification_sent(repo, fascicolo_id):
        raise ValueError("NOTIFICA_EFFETTUATA richiede evento notifica SENT.")
    if target_state == "PROVA_NOTIFICA_ACQUISITA" and not _has_notification_proof(repo, fascicolo_id):
        raise ValueError("PROVA_NOTIFICA_ACQUISITA richiede evidence_documents collegati.")
    if target_state == "CHIUSA" and _has_pending_obligations(repo, fascicolo_id):
        raise ValueError("CHIUSA non possibile con obblighi post-accettazione pendenti.")


def open_workflow_instance(
    repo: ProcedureLifecycleRepository,
    *,
    fascicolo_id: str,
    template_id: int,
    procedure_code: str,
    xsd_code: str | None,
    assigned_lawyer_id: str = "",
    risk_level: str = "MEDIUM",
) -> int:
    return repo.create_workflow_instance(
        {
            "fascicolo_id": fascicolo_id,
            "template_id": template_id,
            "procedure_code": procedure_code,
            "xsd_code": xsd_code,
            "current_step_code": "PRATICA_APERTA",
            "status": "OPEN",
            "assigned_lawyer_id": assigned_lawyer_id or None,
            "risk_level": risk_level,
        }
    )


def transition_workflow(
    repo: ProcedureLifecycleRepository,
    workflow_instance_id: int,
    target_state: str,
    *,
    actor: str = "",
    notes: str = "",
) -> None:
    instance = repo.get_workflow_instance(workflow_instance_id)
    if not instance:
        raise ValueError("Workflow non trovato.")
    current = str(instance.get("current_step_code") or "PRATICA_APERTA")
    _assert_transition_allowed(current, target_state)
    _assert_severe_rules(repo, instance, target_state)
    repo.update_workflow_instance_state(
        workflow_instance_id,
        current_step_code=target_state,
        status=_workflow_status_for_state(target_state),
        close=target_state == "CHIUSA",
        actor=actor,
        notes=notes,
    )
    repo.add_workflow_event(
        {
            "workflow_instance_id": workflow_instance_id,
            "event_code": target_state,
            "event_type": "STATE_TRANSITION",
            "event_status": "RECORDED",
            "event_payload_json": {"from": current, "to": target_state},
            "created_by": actor,
            "notes": notes,
        },
        actor=actor,
    )


def build_lifecycle_steps_for_xsd(xsd_code: str | None) -> list[str]:
    prefix = _prefix(xsd_code)
    if prefix in {"010", "050"}:
        return [
            "CLASSIFICATION",
            "DOCUMENT_COLLECTION",
            "ACT_DRAFT",
            "LEGAL_REVIEW",
            "SIGNATURE_DECISION",
            "SIGNATURE",
            "PACKAGE_BUILD",
            "PACKAGE_VALIDATE",
            "DEPOSIT_SEND",
            "RECEIPT_WAIT",
            "ACCEPTANCE_CHECK",
            "MONITORING",
            "POST_ACCEPTANCE_REVIEW",
            "NOTIFICATION_DECISION",
            "NOTIFICATION",
            "RELATA",
            "PROOF_COLLECTION",
            "PROOF_DEPOSIT",
            "MONITORING",
            "CLOSURE",
        ]
    if prefix == "030":
        return [
            "CLASSIFICATION",
            "DOCUMENT_COLLECTION",
            "ACT_DRAFT",
            "LEGAL_REVIEW",
            "NOTIFICATION_DECISION",
            "RELATA",
            "NOTIFICATION",
            "PROOF_COLLECTION",
            "SIGNATURE_DECISION",
            "SIGNATURE",
            "PACKAGE_BUILD",
            "PACKAGE_VALIDATE",
            "DEPOSIT_SEND",
            "RECEIPT_WAIT",
            "ACCEPTANCE_CHECK",
            "MONITORING",
            "CLOSURE",
        ]
    if prefix in CAUTELARI_PREFIXES:
        return [
            "CLASSIFICATION",
            "DOCUMENT_COLLECTION",
            "ACT_DRAFT",
            "LEGAL_REVIEW",
            "SIGNATURE_DECISION",
            "SIGNATURE",
            "PACKAGE_BUILD",
            "PACKAGE_VALIDATE",
            "DEPOSIT_SEND",
            "RECEIPT_WAIT",
            "ACCEPTANCE_CHECK",
            "POST_ACCEPTANCE_REVIEW",
            "NOTIFICATION_DECISION",
            "MONITORING",
            "CLOSURE",
        ]
    if prefix == "020":
        return [
            "CLASSIFICATION",
            "DOCUMENT_COLLECTION",
            "ACT_DRAFT",
            "LEGAL_REVIEW",
            "SIGNATURE_DECISION",
            "SIGNATURE",
            "PACKAGE_BUILD",
            "PACKAGE_VALIDATE",
            "DEPOSIT_SEND",
            "RECEIPT_WAIT",
            "ACCEPTANCE_CHECK",
            "POST_ACCEPTANCE_REVIEW",
            "NOTIFICATION_DECISION",
            "PROOF_COLLECTION",
            "MONITORING",
            "CLOSURE",
        ]
    return [
        "CLASSIFICATION",
        "DOCUMENT_COLLECTION",
        "ACT_DRAFT",
        "LEGAL_REVIEW",
        "SIGNATURE_DECISION",
        "SIGNATURE",
        "PACKAGE_BUILD",
        "PACKAGE_VALIDATE",
        "DEPOSIT_SEND",
        "RECEIPT_WAIT",
        "ACCEPTANCE_CHECK",
        "POST_ACCEPTANCE_REVIEW",
        "MONITORING",
        "CLOSURE",
    ]


def generate_lifecycle_template_for_xsd(repo: ProcedureLifecycleRepository, xsd_object: dict[str, Any]) -> int:
    candidate = infer_mapping_for_xsd(xsd_object)
    risk_level = "HIGH" if _prefix(candidate.xsd_code) == "050" else "MEDIUM"
    template_id = repo.create_lifecycle_template(
        {
            "procedure_code": candidate.procedure_code,
            "xsd_code": candidate.xsd_code,
            "channel_code": candidate.channel_code,
            "registry_code": candidate.registry_code,
            "workflow_code": candidate.workflow_code,
            "name": f"Lifecycle {xsd_object.get('xsd_label') or candidate.xsd_code}",
            "requires_human_review": 1,
            "notes": f"Template minimo {risk_level}, stato needs_review fino a validazione avvocato.",
        }
    )
    seen: dict[str, int] = {}
    steps = build_lifecycle_steps_for_xsd(candidate.xsd_code)
    for index, step_type in enumerate(steps, start=1):
        seen[step_type] = seen.get(step_type, 0) + 1
        suffix = "" if seen[step_type] == 1 else f"_{seen[step_type]}"
        repo.add_lifecycle_step(
            {
                "template_id": template_id,
                "step_code": f"{step_type}{suffix}",
                "step_name": STEP_LABELS[step_type],
                "step_type": step_type,
                "sort_order": index * 10,
                "required": 1,
                "human_review_required": 1 if step_type in {"LEGAL_REVIEW", "POST_ACCEPTANCE_REVIEW", "NOTIFICATION_DECISION"} else 0,
            }
        )
    return template_id


def generate_lifecycle_templates_for_catalog(repo: ProcedureLifecycleRepository, dry_run: bool = True) -> LifecycleTemplateReport:
    repo.ensure_extended_schema()
    xsd_objects = repo.list_xsd_objects(active_only=True)
    generated = 0
    for xsd_object in xsd_objects:
        if dry_run:
            generated += 1
            continue
        existing = repo.list_lifecycle_templates(xsd_code=str(xsd_object["xsd_code"]))
        if existing:
            continue
        generate_lifecycle_template_for_xsd(repo, xsd_object)
        generated += 1
    return LifecycleTemplateReport(
        dry_run=dry_run,
        xsd_total=len(xsd_objects),
        templates_generated=generated,
        needs_review=generated,
    )
