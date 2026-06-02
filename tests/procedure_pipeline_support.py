from __future__ import annotations

import json
from pathlib import Path

from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig
from pct.procedure_inventory_importer import import_xsd_objects
from pct.procedure_lifecycle import generate_lifecycle_templates_for_catalog
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository
from pct.procedure_xsd_mapper import map_all_xsd_objects


def make_repo(tmp_path: Path) -> ProcedureLifecycleRepository:
    repo = ProcedureLifecycleRepository(CoverageSqliteConfig(str(tmp_path / "coverage.db")))
    repo.ensure_extended_schema()
    return repo


def write_catalog(tmp_path: Path) -> Path:
    catalog = {
        "versione": "test-xsd",
        "fonte": {
            "nome": "PST Test",
            "url": "https://pst.giustizia.it/PST/it/download.page",
            "fileFontePrevalente": "tipi-base.xsd",
        },
        "areas": [
            {
                "area": "procedimenti_speciali_sommari",
                "label": "Procedimenti speciali sommari",
                "items": [
                    {
                        "codice": "010",
                        "label": "Procedimento di ingiunzione ante causam",
                        "children": [{"codice": "010001", "label": "Ingiunzione test"}],
                    },
                    {"codice": "100", "label": "Item senza children"},
                    {"codice": "030", "label": "Sfratto", "children": [{"codice": "030001", "label": "Sfratto test"}]},
                    {"codice": "011", "label": "Cautelare", "children": [{"codice": "011001", "label": "Sequestro"}]},
                    {"codice": "020", "label": "Possessorio", "children": [{"codice": "020001", "label": "Possessorio"}]},
                    {"codice": "050", "label": "Ingiunzione societaria", "children": [{"codice": "050001", "label": "Ingiunzione societaria"}]},
                ],
            }
        ],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return path


def seed_inventory(repo: ProcedureLifecycleRepository, tmp_path: Path) -> Path:
    path = write_catalog(tmp_path)
    import_xsd_objects(repo, str(path), dry_run=False)
    map_all_xsd_objects(repo, dry_run=False)
    generate_lifecycle_templates_for_catalog(repo, dry_run=False)
    return path


def build_complete_notification_proof_bundle(
    repo: ProcedureLifecycleRepository,
    *,
    notification_id: int,
    bundle_id: str = "proof-bundle",
    bundle_type: str = "NOTIFICA_AVVOCATO_PEC",
) -> dict[str, object]:
    from pct.evidence_vault import add_evidence_document
    from pct.notification_proof_matrix import (
        add_notification_dati_atto_receipt_ref,
        add_notification_message,
        add_notification_proof_deposit,
        add_notification_receipt,
        add_notification_relata,
        create_notification_proof_bundle,
        link_notification_evidence,
    )

    notification = repo.get_notification_event(notification_id)
    assert notification is not None
    recipients = repo.list_notification_recipients(notification_id) if hasattr(repo, "list_notification_recipients") else []
    if not recipients:
        with repo.connect() as conn:
            from pct.notification_proof_matrix import ensure_notification_case_graph

            ensure_notification_case_graph(repo, conn, notification_id, notification)
            conn.commit()
        with repo.connect() as conn:
            recipients = repo._fetch_all(
                conn,
                """
                SELECT r.* FROM notification_recipients r
                JOIN notification_cases c ON c.id = r.notification_case_id
                WHERE c.notification_event_id = ?
                ORDER BY r.id
                """,
                (notification_id,),
            )
    recipient_id = int(recipients[0]["id"])
    add_notification_message(
        repo,
        {
            "notification_event_id": notification_id,
            "recipient_id": recipient_id,
            "direction": "OUTBOUND",
            "channel": "PEC",
            "message_id": "<msg-notifica@pec>",
            "sender": "studio@example.pec.it",
            "recipients_to": [notification.get("recipient_address")],
            "subject": "Notifica ai sensi della L. 53/1994",
            "sent_at": "2026-06-02T10:00:00+02:00",
            "raw_eml_document_id": "pec-inviata.eml",
            "body_hash": "1" * 64,
        },
    )
    add_notification_relata(
        repo,
        {
            "notification_event_id": notification_id,
            "recipient_id": recipient_id,
            "relata_type": "AVVOCATO_PEC",
            "document_id": "relata.pdf.p7m",
            "signed_file_document_id": "relata.pdf.p7m",
            "signature_status": "VERIFIED",
            "related_act_document_id": notification.get("act_document_id"),
            "related_recipient_id": recipient_id,
            "validation_status": "VERIFIED",
        },
    )
    acceptance_receipt_id = add_notification_receipt(
        repo,
        {
            "notification_event_id": notification_id,
            "recipient_id": recipient_id,
            "receipt_type": "ACCETTAZIONE",
            "receipt_completeness": "COMPLETA",
            "original_message_id": "<msg-notifica@pec>",
            "receipt_message_id": "<ra@pec>",
            "recipient": notification.get("recipient_address"),
            "event_time": "2026-06-02T10:00:10+02:00",
            "raw_eml_document_id": "accettazione.eml",
            "daticert_xml_document_id": "daticert-accettazione.xml",
            "hash": "2" * 64,
            "verification_status": "VERIFIED",
            "correlation_status": "CORRELATED",
        },
    )
    delivery_receipt_id = add_notification_receipt(
        repo,
        {
            "notification_event_id": notification_id,
            "recipient_id": recipient_id,
            "receipt_type": "AVVENUTA_CONSEGNA",
            "receipt_completeness": "COMPLETA",
            "original_message_id": "<msg-notifica@pec>",
            "receipt_message_id": "<rac@pec>",
            "recipient": notification.get("recipient_address"),
            "event_time": "2026-06-02T10:00:20+02:00",
            "raw_eml_document_id": "consegna.eml",
            "daticert_xml_document_id": "daticert-consegna.xml",
            "original_message_attached_document_id": "postacert.eml",
            "hash": "3" * 64,
            "verification_status": "VERIFIED",
            "correlation_status": "CORRELATED",
        },
    )
    proof_bundle_id = create_notification_proof_bundle(
        repo,
        {
            "notification_event_id": notification_id,
            "recipient_id": recipient_id,
            "bundle_id": bundle_id,
            "bundle_type": bundle_type,
        },
    )
    roles = [
        ("ATTO_NOTIFICATO", "atto-notificato", "4"),
        ("RELATA", "relata", "5"),
        ("PEC_INVIATA", "pec-inviata", "6"),
        ("RICEVUTA_ACCETTAZIONE", "accettazione", "7"),
        ("RICEVUTA_AVVENUTA_CONSEGNA", "consegna", "8"),
    ]
    if bundle_type == "DEPOSITO_PROVA_NOTIFICA":
        roles.extend(
            [
                ("DATI_ATTO_XML", "dati-atto", "9"),
                ("BUSTA_DEPOSITO_PROVA", "busta-deposito-prova", "a"),
                ("RICEVUTA_DEPOSITO_ACCETTAZIONE", "ricevuta-deposito", "b"),
                ("ESITO_DEPOSITO_UFFICIO", "esito-ufficio", "c"),
            ]
        )
    evidence_ids: dict[str, int] = {}
    for role, document_id, char in roles:
        evidence_id = add_evidence_document(
            repo,
            fascicolo_id=str(notification["fascicolo_id"]),
            evidence_type=role,
            document_id=document_id,
            hash=char * 64,
        )
        evidence_ids[role] = evidence_id
        link_notification_evidence(
            repo,
            bundle_id=proof_bundle_id,
            evidence_id=evidence_id,
            evidence_role=role,
            recipient_id=recipient_id,
        )
    if bundle_type == "DEPOSITO_PROVA_NOTIFICA":
        add_notification_proof_deposit(
            repo,
            {
                "notification_event_id": notification_id,
                "bundle_id": proof_bundle_id,
                "deposit_status": "OFFICE_ACCEPTED",
                "dati_atto_xml_id": "DatiAtto.xml",
                "package_document_id": "busta-deposito.enc",
                "accepted_receipt_document_id": "ricevuta-deposito.eml",
                "official_outcome_document_id": "esito-ufficio.xml",
            },
        )
        for receipt_id, receipt_type in (
            (acceptance_receipt_id, "ACCETTAZIONE"),
            (delivery_receipt_id, "AVVENUTA_CONSEGNA"),
        ):
            add_notification_dati_atto_receipt_ref(
                repo,
                {
                    "notification_event_id": notification_id,
                    "recipient_id": recipient_id,
                    "receipt_id": receipt_id,
                    "receipt_type": receipt_type,
                    "message_id": "<msg-notifica@pec>",
                    "event_time": "2026-06-02T10:00:10+02:00",
                    "recipient_address": notification.get("recipient_address"),
                    "source_xml_path": "DatiAtto.xml",
                    "validation_status": "VERIFIED",
                },
            )
    return {
        "bundle_id": proof_bundle_id,
        "recipient_id": recipient_id,
        "acceptance_receipt_id": acceptance_receipt_id,
        "delivery_receipt_id": delivery_receipt_id,
        "evidence_ids": evidence_ids,
    }
