"""Matrice probatoria per PEC, notifiche e deposito prova.

Il proof_bundle_id resta solo un identificativo di contenitore: la prova nasce
da evidenze reali, hashate, correlate al fascicolo, alla notifica e al singolo
destinatario.
"""

from __future__ import annotations

import json
import re
from typing import Any


RECIPIENT_STATUSES = {
    "DRAFT",
    "ADDRESS_PENDING",
    "ADDRESS_VERIFIED",
    "READY",
    "SENT",
    "ACCEPTANCE_RECEIVED",
    "DELIVERY_RECEIVED",
    "DELIVERY_FAILED",
    "ACCEPTANCE_FAILED",
    "PROOF_PARTIAL",
    "PROOF_COMPLETE",
    "REMEDIATION_REQUIRED",
    "CANCELLED",
    "ERROR",
    "NEEDS_REVIEW",
}
RECEIPT_TYPES = {
    "ACCETTAZIONE",
    "AVVENUTA_CONSEGNA",
    "MANCATA_ACCETTAZIONE",
    "MANCATA_CONSEGNA",
    "PRESA_IN_CARICO",
    "ERRORE",
    "ANOMALIA",
    "AVVISO",
    "ALTRO_NEEDS_REVIEW",
}
NEGATIVE_RECEIPT_TYPES = {"MANCATA_ACCETTAZIONE", "MANCATA_CONSEGNA"}
RECEIPT_COMPLETENESS = {"COMPLETA", "BREVE", "SINTETICA", "UNKNOWN"}
RECEIPT_VERIFICATION_STATUSES = {
    "VERIFIED",
    "PARSED_UNVERIFIED",
    "MALFORMED",
    "MISMATCH_MESSAGE_ID",
    "MISMATCH_RECIPIENT",
    "WRONG_FASCICOLO",
    "WRONG_NOTIFICATION",
    "DUPLICATE",
    "NEEDS_REVIEW",
    "ERROR",
}
RECEIPT_CORRELATION_STATUSES = {
    "CORRELATED",
    "NEEDS_REVIEW",
    "MISMATCH_MESSAGE_ID",
    "MISMATCH_RECIPIENT",
    "WRONG_FASCICOLO",
    "WRONG_NOTIFICATION",
    "DUPLICATE",
    "ERROR",
}
RELATA_TYPES = {"AVVOCATO_PEC", "UNEP_XML", "UNEP_SIGNED", "CARTACEA_IMPORTATA", "ALTRO"}
RELATA_VALIDATION_STATUSES = {"VERIFIED", "PARSED_UNVERIFIED", "MISSING_SIGNATURE", "MISSING_DOCUMENT", "NEEDS_REVIEW", "ERROR"}
PROOF_BUNDLE_TYPES = {"NOTIFICA_AVVOCATO_PEC", "NOTIFICA_UNEP", "DEPOSITO_PROVA_NOTIFICA", "ALTRO"}
PROOF_DEPOSIT_STATUSES = {
    "DRAFT",
    "READY",
    "SIGNATURE_REQUIRED",
    "SIGNED",
    "PACKAGE_BUILT",
    "PACKAGE_VALIDATED",
    "SENT",
    "PEC_ACCEPTED",
    "PEC_DELIVERED",
    "CONTROLS_RECEIVED",
    "OFFICE_ACCEPTED",
    "OFFICE_REJECTED",
    "TECHNICAL_ERROR",
    "CANCELLED",
    "NEEDS_REVIEW",
}
REQUIRED_NOTIFICATION_EVIDENCE = {
    "ATTO_NOTIFICATO",
    "RELATA",
    "PEC_INVIATA",
    "RICEVUTA_ACCETTAZIONE",
    "RICEVUTA_AVVENUTA_CONSEGNA",
}
REQUIRED_PROOF_DEPOSIT_EVIDENCE = REQUIRED_NOTIFICATION_EVIDENCE | {
    "DATI_ATTO_XML",
    "BUSTA_DEPOSITO_PROVA",
    "RICEVUTA_DEPOSITO_ACCETTAZIONE",
    "ESITO_DEPOSITO_UFFICIO",
}


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _all(rows: Any) -> list[dict[str, Any]]:
    return [_row(row) or {} for row in rows]


def _is_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{64}", str(value or "").strip()))


def _err(message: str) -> ValueError:
    return ValueError(f"Catena probatoria notifica incompleta: {message}")


def _assert_allowed(value: Any, allowed: set[str], field_name: str) -> None:
    if str(value or "") not in allowed:
        raise ValueError(f"{field_name} non ammesso: {value}")


def fetch_notification_case_for_event(conn: Any, notification_id: int) -> dict[str, Any] | None:
    return _row(
        conn.execute(
            "SELECT * FROM notification_cases WHERE notification_event_id = ? ORDER BY id LIMIT 1",
            (notification_id,),
        ).fetchone()
    )


def ensure_notification_case_graph(repo: Any, conn: Any, notification_id: int, event: dict[str, Any] | None = None) -> dict[str, Any]:
    event_row = event or repo.get_notification_event(notification_id, conn=conn)
    if not event_row:
        raise ValueError("Notifica non trovata.")
    case_status = str(event_row.get("status") or "DRAFT")
    if case_status == "DELIVERED":
        case_status = "DELIVERY_RECEIVED"
    if case_status == "FAILED":
        case_status = "ERROR"
    if case_status in {"PROOF_ACQUIRED", "PROOF_DEPOSIT_REQUIRED", "PROOF_DEPOSITED"}:
        case_status = "PROOF_COMPLETE"
    case = fetch_notification_case_for_event(conn, notification_id)
    if case is None:
        cur = conn.execute(
            """
            INSERT INTO notification_cases (
                tenant_id, fascicolo_id, notification_event_id, case_uid,
                case_type, status, act_document_id, proof_bundle_id, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                event_row.get("tenant_id"),
                event_row["fascicolo_id"],
                notification_id,
                f"notification-event-{notification_id}",
                event_row["notification_type"],
                case_status,
                event_row["act_document_id"],
                event_row.get("proof_bundle_id"),
            ),
        )
        case_id = int(cur.lastrowid)
        case = repo._fetch_one(conn, "SELECT * FROM notification_cases WHERE id = ?", (case_id,)) or {}
        repo.audit_log(entity_type="notification_cases", entity_id=case_id, action="notification_case_create", after=case, source="notification_matrix", conn=conn)
    else:
        conn.execute(
            "UPDATE notification_cases SET status = ?, proof_bundle_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (case_status, event_row.get("proof_bundle_id"), int(case["id"])),
        )
        case = repo._fetch_one(conn, "SELECT * FROM notification_cases WHERE id = ?", (int(case["id"]),)) or {}
    recipient = repo._fetch_one(conn, "SELECT * FROM notification_recipients WHERE notification_event_id = ? ORDER BY id LIMIT 1", (notification_id,))
    recipient_status = case_status if case_status in RECIPIENT_STATUSES else "NEEDS_REVIEW"
    if recipient is None:
        cur = conn.execute(
            """
            INSERT INTO notification_recipients (
                tenant_id, notification_case_id, notification_event_id, fascicolo_id,
                recipient_name, recipient_tax_code, recipient_address,
                recipient_address_source, recipient_type, status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'ALTRO', ?, CURRENT_TIMESTAMP)
            """,
            (
                event_row.get("tenant_id"),
                int(case["id"]),
                notification_id,
                event_row["fascicolo_id"],
                event_row.get("recipient_name"),
                event_row.get("recipient_tax_code"),
                event_row.get("recipient_address"),
                event_row.get("recipient_address_source"),
                recipient_status,
            ),
        )
        recipient_id = int(cur.lastrowid)
        after = repo._fetch_one(conn, "SELECT * FROM notification_recipients WHERE id = ?", (recipient_id,))
        repo.audit_log(entity_type="notification_recipients", entity_id=recipient_id, action="notification_recipient_create", after=after, source="notification_matrix", conn=conn)
    else:
        conn.execute(
            """
            UPDATE notification_recipients
            SET notification_case_id = ?, recipient_name = ?, recipient_tax_code = ?,
                recipient_address = ?, recipient_address_source = ?, status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                int(case["id"]),
                event_row.get("recipient_name"),
                event_row.get("recipient_tax_code"),
                event_row.get("recipient_address"),
                event_row.get("recipient_address_source"),
                recipient_status,
                int(recipient["id"]),
            ),
        )
    return case


def validate_notification_proof_bundle(
    conn: Any,
    *,
    fascicolo_id: str,
    proof_bundle_id: Any,
    notification_id: int | None = None,
    target_status: str = "",
) -> None:
    bundle_id = str(proof_bundle_id or "").strip()
    if not bundle_id:
        raise _err("proof_bundle_id indica solo il contenitore e non può essere vuoto.")
    bundle = _row(conn.execute("SELECT * FROM notification_proof_bundles WHERE fascicolo_id = ? AND bundle_id = ? LIMIT 1", (fascicolo_id, bundle_id)).fetchone())
    if not bundle:
        raise _err("proof_bundle_id deve puntare a notification_proof_bundles, non a una ricevuta generica.")
    if str(bundle.get("validation_status") or "") != "VERIFIED":
        raise _err("il bundle prova deve essere in stato VERIFIED.")
    case = _row(conn.execute("SELECT * FROM notification_cases WHERE id = ?", (int(bundle.get("notification_case_id") or 0),)).fetchone())
    if not case:
        raise _err("il bundle deve essere collegato a un caso notifica.")
    if notification_id is not None and int(case.get("notification_event_id") or 0) != int(notification_id):
        raise _err("il bundle appartiene a un'altra notifica.")
    required = set(REQUIRED_NOTIFICATION_EVIDENCE)
    proof_deposit_required = str(target_status or "") == "PROOF_DEPOSITED" or str(bundle.get("bundle_type") or "") == "DEPOSITO_PROVA_NOTIFICA"
    if proof_deposit_required:
        required = set(REQUIRED_PROOF_DEPOSIT_EVIDENCE)
    links = _all(
        conn.execute(
            """
            SELECT l.*, e.fascicolo_id AS evidence_fascicolo_id, e.hash AS evidence_hash
            FROM notification_evidence_links l
            JOIN evidence_documents e ON e.id = l.evidence_document_id
            WHERE l.bundle_id = ?
            """,
            (bundle_id,),
        ).fetchall()
    )
    roles = {str(link.get("evidence_role") or "") for link in links if str(link.get("validation_status") or "") == "VERIFIED"}
    missing = sorted(required - roles)
    if missing:
        raise _err("mancano evidenze distinte: " + ", ".join(missing) + ".")
    for link in links:
        if str(link.get("evidence_fascicolo_id") or "") != str(fascicolo_id or ""):
            raise _err("una evidenza del bundle appartiene a un altro fascicolo.")
        if str(link.get("validation_status") or "") != "VERIFIED":
            raise _err("ogni evidenza del bundle deve essere VERIFIED.")
        if not _is_sha256(link.get("document_hash") or link.get("evidence_hash")):
            raise _err("ogni evidenza deve avere hash SHA-256 valido.")
    recipients = _all(conn.execute("SELECT * FROM notification_recipients WHERE notification_case_id = ? AND status <> 'CANCELLED'", (int(case["id"]),)).fetchall())
    if not recipients:
        raise _err("il caso notifica deve avere almeno un destinatario.")
    for recipient in recipients:
        receipts = _all(conn.execute("SELECT * FROM notification_receipts WHERE notification_case_id = ? AND recipient_id = ?", (int(case["id"]), int(recipient["id"]))).fetchall())
        verified_types = {
            str(row.get("receipt_type") or "")
            for row in receipts
            if str(row.get("verification_status") or "") == "VERIFIED"
            and str(row.get("correlation_status") or "") == "CORRELATED"
        }
        negative_types = verified_types & NEGATIVE_RECEIPT_TYPES
        if negative_types:
            raise _err("la ricevuta negativa richiede remediation e non prova positiva: " + ", ".join(sorted(negative_types)) + ".")
        if "ACCETTAZIONE" not in verified_types:
            raise _err("manca la ricevuta di accettazione verificata per destinatario.")
        if "AVVENUTA_CONSEGNA" not in verified_types:
            raise _err("manca la ricevuta di avvenuta consegna verificata per destinatario.")
        recipient_link_roles = {
            str(link.get("evidence_role") or "")
            for link in links
            if str(link.get("validation_status") or "") == "VERIFIED"
            and int(link.get("recipient_id") or 0) == int(recipient["id"])
        }
        for receipt_role in ("RICEVUTA_ACCETTAZIONE", "RICEVUTA_AVVENUTA_CONSEGNA"):
            if receipt_role not in recipient_link_roles:
                raise _err("manca evidenza ricevuta collegata al destinatario: " + receipt_role + ".")
        if str(recipient.get("status") or "") not in {"DELIVERY_RECEIVED", "PROOF_COMPLETE"}:
            raise _err("il destinatario deve essere in DELIVERY_RECEIVED o PROOF_COMPLETE.")
    message = _row(
        conn.execute(
            """
            SELECT * FROM notification_messages
            WHERE notification_case_id = ?
              AND direction = 'OUTBOUND'
              AND COALESCE(message_id, '') <> ''
              AND COALESCE(raw_eml_document_id, '') <> ''
              AND COALESCE(body_hash, '') <> ''
            LIMIT 1
            """,
            (int(case["id"]),),
        ).fetchone()
    )
    if not message or not _is_sha256(message.get("body_hash")):
        raise _err("manca il messaggio PEC inviato originale con Message-ID, EML e hash.")
    relata = _row(conn.execute("SELECT * FROM notification_relata WHERE notification_case_id = ? AND validation_status = 'VERIFIED' AND COALESCE(document_id, '') <> '' LIMIT 1", (int(case["id"]),)).fetchone())
    if not relata:
        raise _err("manca la relata verificata collegata al caso.")
    if proof_deposit_required:
        deposit = _row(
            conn.execute(
                """
                SELECT * FROM notification_proof_deposits
                WHERE notification_case_id = ?
                  AND bundle_id = ?
                  AND deposit_status = 'OFFICE_ACCEPTED'
                  AND COALESCE(dati_atto_xml_id, '') <> ''
                  AND COALESCE(package_document_id, '') <> ''
                  AND (COALESCE(accepted_receipt_document_id, '') <> '' OR COALESCE(official_outcome_document_id, '') <> '')
                LIMIT 1
                """,
                (int(case["id"]), bundle_id),
            ).fetchone()
        )
        if not deposit:
            raise _err("PROOF_DEPOSITED richiede deposito prova accettato dall'ufficio.")
        for recipient in recipients:
            for receipt_type in ("ACCETTAZIONE", "AVVENUTA_CONSEGNA"):
                ref = _row(
                    conn.execute(
                        """
                        SELECT ref.*
                        FROM notification_dati_atto_receipt_refs ref
                        JOIN notification_receipts receipt ON receipt.id = ref.receipt_id
                        WHERE ref.notification_case_id = ?
                          AND ref.recipient_id = ?
                          AND ref.receipt_type = ?
                          AND ref.validation_status = 'VERIFIED'
                          AND receipt.notification_case_id = ref.notification_case_id
                          AND receipt.recipient_id = ref.recipient_id
                          AND receipt.receipt_type = ref.receipt_type
                          AND receipt.verification_status = 'VERIFIED'
                          AND receipt.correlation_status = 'CORRELATED'
                        LIMIT 1
                        """,
                        (int(case["id"]), int(recipient["id"]), receipt_type),
                    ).fetchone()
                )
                if not ref:
                    raise _err("DatiAtto.xml deve contenere riferimenti ricevuta per ogni destinatario.")


def add_notification_message(repo: Any, row: dict[str, Any], *, actor: str = "", source: str = "notification_matrix") -> int:
    repo.ensure_extended_schema()
    with repo.connect() as conn:
        case = ensure_notification_case_graph(repo, conn, int(row["notification_event_id"]))
        cur = conn.execute(
            """
            INSERT INTO notification_messages (
                tenant_id, fascicolo_id, notification_case_id, recipient_id,
                direction, channel, message_id, in_reply_to, references_header,
                sender, recipients_to, recipients_cc, recipients_bcc_hash_only,
                subject, sent_at, received_at, raw_eml_document_id, raw_msg_document_id,
                body_hash, attachments_json, parsed_payload_json,
                parse_status, verification_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                row.get("tenant_id"),
                case["fascicolo_id"],
                int(case["id"]),
                row.get("recipient_id"),
                row.get("direction", "OUTBOUND"),
                row.get("channel", "PEC"),
                row.get("message_id"),
                row.get("in_reply_to"),
                row.get("references"),
                row.get("sender"),
                _dumps(row.get("recipients_to", [])),
                _dumps(row.get("recipients_cc", [])),
                row.get("recipients_bcc_hash_only"),
                row.get("subject"),
                row.get("sent_at"),
                row.get("received_at"),
                row.get("raw_eml_document_id"),
                row.get("raw_msg_document_id"),
                row.get("body_hash"),
                _dumps(row.get("attachments_json", [])),
                _dumps(row.get("parsed_payload_json", {})),
                row.get("parse_status", "PARSED"),
                row.get("verification_status", "VERIFIED"),
            ),
        )
        message_id = int(cur.lastrowid)
        after = repo._fetch_one(conn, "SELECT * FROM notification_messages WHERE id = ?", (message_id,))
        repo.audit_log(entity_type="notification_messages", entity_id=message_id, action="notification_message_add", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return message_id


def add_notification_relata(repo: Any, row: dict[str, Any], *, actor: str = "", source: str = "notification_matrix") -> int:
    repo.ensure_extended_schema()
    _assert_allowed(row.get("relata_type", "AVVOCATO_PEC"), RELATA_TYPES, "relata_type")
    _assert_allowed(row.get("validation_status", "NEEDS_REVIEW"), RELATA_VALIDATION_STATUSES, "validation_status")
    with repo.connect() as conn:
        case = ensure_notification_case_graph(repo, conn, int(row["notification_event_id"]))
        cur = conn.execute(
            """
            INSERT INTO notification_relata (
                tenant_id, fascicolo_id, notification_case_id, recipient_id,
                relata_type, document_id, signed_file_document_id,
                signature_status, related_act_document_id, related_recipient_id,
                validation_status, validation_errors_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', CURRENT_TIMESTAMP)
            """,
            (
                row.get("tenant_id"),
                case["fascicolo_id"],
                int(case["id"]),
                row.get("recipient_id"),
                row.get("relata_type", "AVVOCATO_PEC"),
                row.get("document_id"),
                row.get("signed_file_document_id"),
                row.get("signature_status"),
                row.get("related_act_document_id"),
                row.get("related_recipient_id"),
                row.get("validation_status", "NEEDS_REVIEW"),
            ),
        )
        relata_id = int(cur.lastrowid)
        after = repo._fetch_one(conn, "SELECT * FROM notification_relata WHERE id = ?", (relata_id,))
        repo.audit_log(entity_type="notification_relata", entity_id=relata_id, action="notification_relata_add", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return relata_id


def add_notification_receipt(repo: Any, row: dict[str, Any], *, actor: str = "", source: str = "notification_matrix") -> int:
    repo.ensure_extended_schema()
    receipt_type = str(row.get("receipt_type") or "")
    _assert_allowed(receipt_type, RECEIPT_TYPES, "receipt_type")
    _assert_allowed(row.get("receipt_completeness", "UNKNOWN"), RECEIPT_COMPLETENESS, "receipt_completeness")
    _assert_allowed(row.get("verification_status", "NEEDS_REVIEW"), RECEIPT_VERIFICATION_STATUSES, "verification_status")
    _assert_allowed(row.get("correlation_status", "NEEDS_REVIEW"), RECEIPT_CORRELATION_STATUSES, "correlation_status")
    with repo.connect() as conn:
        case = ensure_notification_case_graph(repo, conn, int(row["notification_event_id"]))
        recipient_id = int(row["recipient_id"])
        if not repo._fetch_one(conn, "SELECT id FROM notification_recipients WHERE id = ? AND notification_case_id = ?", (recipient_id, int(case["id"]))):
            repo._blocked_operation(conn, entity_type="notification_receipts", entity_id=str(case["id"]), action="notification_receipt_add", reason="La ricevuta deve appartenere al destinatario della notifica.", attempted=row, actor=actor, source=source)
        cur = conn.execute(
            """
            INSERT INTO notification_receipts (
                tenant_id, fascicolo_id, notification_case_id, recipient_id, pec_message_id,
                original_message_id, receipt_message_id, receipt_type, receipt_completeness,
                sender, recipient, event_time, received_at, provider, raw_eml_document_id,
                daticert_xml_document_id, original_message_attached_document_id,
                parsed_payload_json, hash, verification_status, correlation_status,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                row.get("tenant_id"),
                case["fascicolo_id"],
                int(case["id"]),
                recipient_id,
                row.get("pec_message_id"),
                row.get("original_message_id"),
                row.get("receipt_message_id"),
                receipt_type,
                row.get("receipt_completeness", "UNKNOWN"),
                row.get("sender"),
                row.get("recipient"),
                row.get("event_time"),
                row.get("received_at"),
                row.get("provider"),
                row.get("raw_eml_document_id"),
                row.get("daticert_xml_document_id"),
                row.get("original_message_attached_document_id"),
                _dumps(row.get("parsed_payload_json", {})),
                row.get("hash"),
                row.get("verification_status", "NEEDS_REVIEW"),
                row.get("correlation_status", "NEEDS_REVIEW"),
            ),
        )
        receipt_id = int(cur.lastrowid)
        if receipt_type == "AVVENUTA_CONSEGNA" and row.get("verification_status") == "VERIFIED" and row.get("correlation_status") == "CORRELATED":
            recipient_status = "DELIVERY_RECEIVED"
        elif receipt_type == "ACCETTAZIONE" and row.get("verification_status") == "VERIFIED" and row.get("correlation_status") == "CORRELATED":
            recipient_status = "ACCEPTANCE_RECEIVED"
        elif receipt_type in NEGATIVE_RECEIPT_TYPES:
            recipient_status = "REMEDIATION_REQUIRED"
        else:
            recipient_status = "NEEDS_REVIEW"
        conn.execute("UPDATE notification_recipients SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (recipient_status, recipient_id))
        after = repo._fetch_one(conn, "SELECT * FROM notification_receipts WHERE id = ?", (receipt_id,))
        repo.audit_log(entity_type="notification_receipts", entity_id=receipt_id, action="notification_receipt_add", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return receipt_id


def create_notification_proof_bundle(repo: Any, row: dict[str, Any], *, actor: str = "", source: str = "notification_matrix") -> str:
    repo.ensure_extended_schema()
    _assert_allowed(row.get("bundle_type", "NOTIFICA_AVVOCATO_PEC"), PROOF_BUNDLE_TYPES, "bundle_type")
    with repo.connect() as conn:
        case = ensure_notification_case_graph(repo, conn, int(row["notification_event_id"]))
        bundle_id = str(row.get("bundle_id") or f"notification-proof-{case['id']}")
        required = sorted(REQUIRED_PROOF_DEPOSIT_EVIDENCE if row.get("bundle_type") == "DEPOSITO_PROVA_NOTIFICA" else REQUIRED_NOTIFICATION_EVIDENCE)
        conn.execute(
            """
            INSERT INTO notification_proof_bundles (
                tenant_id, fascicolo_id, notification_case_id, recipient_id, bundle_id,
                bundle_type, required_evidence_json, collected_evidence_json,
                missing_evidence_json, validation_status, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '[]', ?, 'DRAFT', CURRENT_TIMESTAMP)
            """,
            (row.get("tenant_id"), case["fascicolo_id"], int(case["id"]), row.get("recipient_id"), bundle_id, row.get("bundle_type", "NOTIFICA_AVVOCATO_PEC"), _dumps(required), _dumps(required)),
        )
        after = repo._fetch_one(conn, "SELECT * FROM notification_proof_bundles WHERE bundle_id = ?", (bundle_id,))
        repo.audit_log(entity_type="notification_proof_bundles", entity_id=bundle_id, action="notification_proof_bundle_create", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return bundle_id


def _refresh_bundle(repo: Any, conn: Any, bundle_id: str) -> None:
    bundle = repo._fetch_one(conn, "SELECT * FROM notification_proof_bundles WHERE bundle_id = ?", (bundle_id,))
    if not bundle:
        raise ValueError("Bundle prova notifica non trovato.")
    required = set(json.loads(bundle.get("required_evidence_json") or "[]"))
    links = _all(
        conn.execute(
            """
            SELECT l.*, e.hash AS evidence_hash
            FROM notification_evidence_links l
            JOIN evidence_documents e ON e.id = l.evidence_document_id
            WHERE l.bundle_id = ?
            """,
            (bundle_id,),
        ).fetchall()
    )
    collected = sorted({str(row.get("evidence_role") or "") for row in links if str(row.get("validation_status") or "") == "VERIFIED"})
    valid_hashes = all(_is_sha256(row.get("document_hash") or row.get("evidence_hash")) for row in links)
    missing = sorted(required - set(collected))
    status = "VERIFIED" if not missing and valid_hashes else "PARTIAL"
    conn.execute(
        "UPDATE notification_proof_bundles SET collected_evidence_json = ?, missing_evidence_json = ?, validation_status = ?, updated_at = CURRENT_TIMESTAMP WHERE bundle_id = ?",
        (_dumps(collected), _dumps(missing), status, bundle_id),
    )


def link_notification_evidence(repo: Any, *, bundle_id: str, evidence_id: int, evidence_role: str, recipient_id: int | None = None, actor: str = "", source: str = "notification_matrix") -> int:
    repo.ensure_extended_schema()
    with repo.connect() as conn:
        bundle = repo._fetch_one(conn, "SELECT * FROM notification_proof_bundles WHERE bundle_id = ?", (bundle_id,))
        evidence = repo._fetch_one(conn, "SELECT * FROM evidence_documents WHERE id = ?", (int(evidence_id),))
        if not bundle or not evidence:
            repo._blocked_operation(conn, entity_type="notification_evidence_links", entity_id=bundle_id, action="notification_evidence_link", reason="Bundle o evidenza non trovati.", attempted={"bundle_id": bundle_id, "evidence_id": evidence_id}, actor=actor, source=source)
        if str(bundle["fascicolo_id"]) != str(evidence["fascicolo_id"]):
            repo._blocked_operation(conn, entity_type="notification_evidence_links", entity_id=bundle_id, action="notification_evidence_link", reason="Evidenza di altro fascicolo non collegabile al bundle prova.", attempted={"bundle_id": bundle_id, "evidence_id": evidence_id}, actor=actor, source=source)
        document_hash = str(evidence.get("hash") or "")
        if not _is_sha256(document_hash):
            repo._blocked_operation(conn, entity_type="notification_evidence_links", entity_id=bundle_id, action="notification_evidence_link", reason="Evidenza priva di hash SHA-256 valido.", attempted={"bundle_id": bundle_id, "evidence_id": evidence_id}, actor=actor, source=source)
        cur = conn.execute(
            """
            INSERT INTO notification_evidence_links (
                tenant_id, fascicolo_id, bundle_id, notification_case_id, recipient_id,
                evidence_document_id, evidence_role, document_hash, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'VERIFIED')
            """,
            (bundle.get("tenant_id"), bundle["fascicolo_id"], bundle_id, int(bundle["notification_case_id"]), recipient_id, int(evidence_id), evidence_role, document_hash),
        )
        link_id = int(cur.lastrowid)
        _refresh_bundle(repo, conn, bundle_id)
        after = repo._fetch_one(conn, "SELECT * FROM notification_evidence_links WHERE id = ?", (link_id,))
        repo.audit_log(entity_type="notification_evidence_links", entity_id=link_id, action="notification_evidence_link", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return link_id


def add_notification_proof_deposit(repo: Any, row: dict[str, Any], *, actor: str = "", source: str = "notification_matrix") -> int:
    repo.ensure_extended_schema()
    _assert_allowed(row.get("deposit_status", "DRAFT"), PROOF_DEPOSIT_STATUSES, "deposit_status")
    with repo.connect() as conn:
        case = ensure_notification_case_graph(repo, conn, int(row["notification_event_id"]))
        cur = conn.execute(
            """
            INSERT INTO notification_proof_deposits (
                tenant_id, fascicolo_id, notification_case_id, bundle_id, deposit_status,
                dati_atto_xml_id, package_document_id, accepted_receipt_document_id,
                official_outcome_document_id, sent_at, accepted_at, rejected_at,
                technical_error, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (row.get("tenant_id"), case["fascicolo_id"], int(case["id"]), row["bundle_id"], row.get("deposit_status", "DRAFT"), row.get("dati_atto_xml_id"), row.get("package_document_id"), row.get("accepted_receipt_document_id"), row.get("official_outcome_document_id"), row.get("sent_at"), row.get("accepted_at"), row.get("rejected_at"), row.get("technical_error"), row.get("notes")),
        )
        deposit_id = int(cur.lastrowid)
        after = repo._fetch_one(conn, "SELECT * FROM notification_proof_deposits WHERE id = ?", (deposit_id,))
        repo.audit_log(entity_type="notification_proof_deposits", entity_id=deposit_id, action="notification_proof_deposit_add", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return deposit_id


def add_notification_dati_atto_receipt_ref(repo: Any, row: dict[str, Any], *, actor: str = "", source: str = "notification_matrix") -> int:
    repo.ensure_extended_schema()
    _assert_allowed(row.get("receipt_type"), RECEIPT_TYPES, "receipt_type")
    with repo.connect() as conn:
        case = ensure_notification_case_graph(repo, conn, int(row["notification_event_id"]))
        cur = conn.execute(
            """
            INSERT INTO notification_dati_atto_receipt_refs (
                tenant_id, deposit_package_id, notification_case_id, recipient_id,
                receipt_id, receipt_type, message_id, event_time, recipient_address,
                source_xml_path, validation_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (row.get("tenant_id"), row.get("deposit_package_id"), int(case["id"]), int(row["recipient_id"]), int(row["receipt_id"]), row["receipt_type"], row.get("message_id"), row.get("event_time"), row.get("recipient_address"), row.get("source_xml_path"), row.get("validation_status", "VERIFIED")),
        )
        ref_id = int(cur.lastrowid)
        after = repo._fetch_one(conn, "SELECT * FROM notification_dati_atto_receipt_refs WHERE id = ?", (ref_id,))
        repo.audit_log(entity_type="notification_dati_atto_receipt_refs", entity_id=ref_id, action="notification_dati_atto_receipt_ref_add", after=after, actor=actor, source=source, conn=conn)
        conn.commit()
    return ref_id
