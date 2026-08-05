"""Validazione del deposito della prova di notifica.

Questo modulo resta fuori dal motore di creazione della notifica PEC: la
notifica prepara relata, attestazione e invio locale; il deposito della prova
successivo vive qui e nei flussi dedicati al deposito.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct.notifiche_legali import (
    PUBLIC_PEC_REGISTERS,
    SHA256_HEX_RE,
    LegalWorkflowResult,
    _check_row,
    block,
    boolish,
    build_notification_evidence_pack,
    normalise_public_register,
    template_catalog_version,
    text,
)


PROVA_DEPOSITO_NOTIFICA_STEPS: tuple[dict[str, str], ...] = (
    {
        "id": "pacchetto_prova_deposito",
        "title": "Pacchetto prova e deposito",
        "body": "Dopo l'invio si conservano PEC inviata, RAC e RdAC complete in originale digitale e si prepara l'indicizzazione per il deposito.",
        "source": "L. 53/1994, art. 9; Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
    },
    {
        "id": "atti",
        "title": "Raccolta atti notificati",
        "body": "La prova può includere più atti o allegati notificati, con nome e impronta del file.",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
    },
    {
        "id": "ricevute",
        "title": "Ricevute originali",
        "body": "Per ogni destinatario servono RAC e RdAC completa in formato originale digitale .eml o .msg.",
        "source": "L. 53/1994, art. 3-bis, comma 3; D.M. 44/2011, art. 18, comma 6",
    },
    {
        "id": "dati_atto",
        "title": "Indicizzazione ricevute",
        "body": "I riferimenti delle ricevute sono preparati per il riepilogo del deposito.",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
    },
    {
        "id": "audit",
        "title": "Audit e controllo finale",
        "body": "Il pacchetto prova registra file, impronte e controlli prima del deposito.",
        "source": "L. 53/1994, art. 9",
    },
)


def build_deposit_normative_checks(payload: dict[str, Any], evidence_pack: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return checks for depositing proof of a PEC notification."""

    evidence_pack = evidence_pack or build_notification_evidence_pack(payload)
    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
        }]
    receipt_files = [
        text(row.get(field))
        for row in recipients
        if isinstance(row, dict)
        for field in ("rac_file", "rdac_file")
    ]
    originals_ok = bool(receipt_files) and all(Path(filename).suffix.lower() in {".eml", ".msg"} for filename in receipt_files)
    return [
        _check_row(
            id="atti_notificati",
            label="Atti notificati",
            source="Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
            passed=bool(payload.get("atti_notificati") or text(payload.get("atto_notificato"))),
            detail="L'atto notificato viene inserito nella busta con gli allegati necessari.",
        ),
        _check_row(
            id="relata_firmata",
            label="Relata firmata",
            source="L. 53/1994, art. 3-bis, comma 5",
            passed=bool(text(payload.get("relata_firmata"))),
            detail="La relata firmata digitalmente va conservata nel pacchetto prova.",
        ),
        _check_row(
            id="pec_inviata",
            label="PEC inviata",
            source="L. 53/1994, art. 3-bis, comma 3",
            passed=bool(text(payload.get("pec_inviata") or payload.get("pec_inviata_file"))),
            detail="Il messaggio inviato resta allegato in originale digitale.",
        ),
        _check_row(
            id="rac_rdac",
            label="RAC e RdAC originali",
            source="L. 53/1994, art. 9; D.M. 44/2011, art. 18, comma 6",
            passed=originals_ok and boolish(payload.get("ricevuta_completa")),
            detail="RAC e RdAC completa devono restare file .eml o .msg per ogni destinatario.",
        ),
        _check_row(
            id="hash",
            label="Impronte dei file",
            source="Audit interno IUSENTRA",
            passed=not evidence_pack.get("missing") and not evidence_pack.get("invalid_hashes"),
            detail="Ogni file richiesto dal pacchetto prova deve avere impronta valida.",
        ),
        _check_row(
            id="dati_atto",
            label="Riferimenti ricevute",
            source="Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
            passed=bool(text(payload.get("dati_atto_ricevute"))),
            detail="I dati identificativi delle ricevute vanno indicizzati nel deposito.",
        ),
    ]


def build_deposit_audit_trail(payload: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
        }]
    return {
        "phase": "deposito_prova",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "documentsCount": len([
            item
            for item in evidence_pack.get("items", [])
            if str(item.get("kind", "")).startswith("atto") or str(item.get("kind", "")).startswith("allegato")
        ]),
        "recipients": [
            {
                "name": text(row.get("nome")),
                "racFile": text(row.get("rac_file")),
                "rdacFile": text(row.get("rdac_file")),
            }
            for row in recipients
            if isinstance(row, dict)
        ],
        "checks": build_deposit_normative_checks(payload, evidence_pack),
        "evidencePack": evidence_pack,
    }


def validate_deposit_notification_proof(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate the evidence pack before deposit of notification proof."""

    blockers: list[str] = []
    warnings: list[str] = []
    notified_documents = payload.get("atti_notificati")
    has_notified_documents = isinstance(notified_documents, list) and bool(notified_documents)
    if not has_notified_documents and not text(payload.get("atto_notificato")):
        blockers.append("Inserisci l'atto notificato da depositare come prova.")
    if not text(payload.get("relata_firmata")):
        blockers.append("Allega la relata firmata digitalmente.")
    if not text(payload.get("pec_inviata") or payload.get("pec_inviata_file")):
        blockers.append("Allega il messaggio PEC inviato in originale digitale.")
    if not boolish(payload.get("ricevuta_completa")) and text(payload.get("rdac_tipo")).lower() != "completa":
        blockers.append(block("RICEVUTA_COMPLETA_REQUIRED", "La prova deposito richiede RdAC completa."))

    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "codice_fiscale_piva": payload.get("destinatario_cf") or payload.get("codice_fiscale_piva"),
            "pec": payload.get("destinatario_pec"),
            "fonte_pec": payload.get("fonte_pec_destinatario"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
            "rac_sha256": payload.get("rac_sha256"),
            "rdac_sha256": payload.get("rdac_sha256"),
        }]
    if not recipients:
        blockers.append("Indica almeno un destinatario della notifica.")

    for index, recipient in enumerate(recipients, start=1):
        if not isinstance(recipient, dict):
            blockers.append(f"Destinatario {index}: dati ricevute non leggibili.")
            continue
        label = text(recipient.get("nome"), f"destinatario {index}")
        recipient_tax_code = text(
            recipient.get("codice_fiscale_piva")
            or recipient.get("codice_fiscale")
            or recipient.get("destinatario_cf")
            or recipient.get("recipient_tax_code")
        )
        recipient_pec = text(
            recipient.get("pec")
            or recipient.get("destinatario_pec")
            or recipient.get("recipient_address")
            or recipient.get("indirizzo_pec")
        )
        recipient_source = normalise_public_register(
            recipient.get("fonte_pec")
            or recipient.get("fonte_pec_destinatario")
            or recipient.get("recipient_address_source")
            or recipient.get("pubblico_elenco")
        )
        if not recipient_tax_code:
            blockers.append(block("DESTINATARIO_CF_REQUIRED", f"{label}: indica codice fiscale o partita IVA del destinatario collegato a RAC e RdAC."))
        if not recipient_pec:
            blockers.append(block("DESTINATARIO_PEC_REQUIRED", f"{label}: indica l'indirizzo PEC destinatario collegato a RAC e RdAC."))
        if recipient_source not in PUBLIC_PEC_REGISTERS:
            blockers.append(block("DESTINATARIO_FONTE_PEC_REQUIRED", f"{label}: indica il pubblico elenco da cui è stata estratta la PEC."))
        for field, human in (("rac_file", "ricevuta di accettazione"), ("rdac_file", "ricevuta di avvenuta consegna completa")):
            filename = text(recipient.get(field))
            if not filename:
                blockers.append(f"{label}: manca la {human}.")
                continue
            if Path(filename).suffix.lower() not in {".eml", ".msg"}:
                blockers.append(f"{label}: conserva la {human} in originale digitale .eml o .msg.")

    evidence_pack = build_notification_evidence_pack(payload)
    blockers.extend(block("EVIDENCE_PACK_REQUIRED", item) for item in evidence_pack["missing"])
    blockers.extend(block("HASH_SHA256_INVALID", item) for item in evidence_pack.get("invalid_hashes", []))

    if not text(payload.get("dati_atto_ricevute")):
        blockers.append(block("DATI_ATTO_RICEVUTE_REQUIRED", "Indica i riferimenti delle ricevute per il deposito."))

    body = (
        "Prova notifica pronta per il controllo: atto notificato, relata firmata, "
        "messaggio PEC inviato, RAC e RdAC originali per ciascun destinatario."
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject="Deposito prova notifica",
        body=body,
        template_id="distinta_prova_notifica",
        template_label="Distinta prova notifica",
        template_version=template_catalog_version(),
        next_actions=(
            "Inserisci atto notificato e ricevute nella busta telematica.",
            "Controlla che RAC e RdAC restino in originale digitale.",
            "Verifica i riferimenti delle ricevute nel riepilogo del deposito.",
        ),
        output_plan={
            "evidencePack": evidence_pack,
            "workflowSteps": [dict(item) for item in PROVA_DEPOSITO_NOTIFICA_STEPS],
            "normativeChecks": build_deposit_normative_checks(payload, evidence_pack),
            "auditTrail": build_deposit_audit_trail(payload, evidence_pack),
        },
        log_json={"evento": "controllo_prova_notifica", "evidencePack": evidence_pack, "audit": build_deposit_audit_trail(payload, evidence_pack)},
    )
