from __future__ import annotations

import json
import sqlite3
from email import policy
from email.message import EmailMessage
from pathlib import Path

import pytest

from pct.pec_notification_presidio import (
    NotificationPresidioRepository,
    NotificationPresidioService,
    NotificationReceiptEnvelope,
    PecNotificationReconciler,
    PresidioStatus,
    Priority,
    ReceiptKind,
)
from pct.pec_notification_presidio.historical_policy import classify_historical_record
from pct.pec_pipeline import PecAuditRepository


def _repo(tmp_path: Path) -> NotificationPresidioRepository:
    return NotificationPresidioRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="tenant-notifiche-test",
    )


def _candidate(
    service: NotificationPresidioService,
    *,
    recipients: list[dict[str, str]],
) -> str:
    result = service.create_candidate(
        {
            "fascicolo_id": "FASC-001",
            "source_message_id": "ordine-notifica-001",
            "source_effective_at": "2026-07-20T10:00:00+02:00",
            "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
            "notification_case": "notifica_l53",
            "rulepack_version": "legal-notification-rulepack-v1",
            "priority": "P1",
            "confidence": 0.99,
            "detection_reason": "Ordine espresso di notifica rilevato.",
            "documents": [
                {
                    "content_sha256": "a" * 64,
                    "original_filename": "Ricorso.pdf",
                    "document_version": "1",
                    "document_role": "notified_act",
                }
            ],
            "recipients": recipients,
        }
    )
    assert result["created"] is True
    return str(result["id"])


def _sent(
    reconciler: PecNotificationReconciler,
    *,
    presidio_id: str,
    message_id: str,
    recipient: dict[str, str],
) -> None:
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.SENT,
            message_id=message_id,
            presidio_id=presidio_id,
            recipient_address=recipient["pec_address"],
            recipient_name=recipient["name"],
            recipient_fiscal_id=recipient["fiscal_id"],
            occurred_at="2026-07-20T10:30:00+02:00",
        )
    )


def _recipient_rows(repo: NotificationPresidioRepository, presidio_id: str) -> list[dict[str, str]]:
    with repo.connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM pec_legal_notification_recipients
            WHERE tenant_id=? AND presidio_id=?
            ORDER BY pec_address
            """,
            (repo.tenant_id, presidio_id),
        ).fetchall()
    return [dict(row) for row in rows]


def test_correzione_decisione_confermata_richiede_motivazione_e_resta_auditabile(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    presidio_id = _candidate(
        NotificationPresidioService(repo),
        recipients=[{"name": "Ministero", "role": "controparte"}],
    )
    repo.transition(
        presidio_id,
        PresidioStatus.NOTIFICATION_CONFIRMED,
        actor="avvocato-test",
        reason="Notifica necessaria confermata dopo la verifica.",
        evidence={"source": "ui_presidio"},
        idempotency_key="conferma-decisione",
    )

    with pytest.raises(ValueError, match="motivazione chiara"):
        repo.transition(
            presidio_id,
            PresidioStatus.NEEDS_REVIEW,
            actor="avvocato-test",
            reason="errore",
            evidence={"source": "ui_presidio", "operation": "decision_revision"},
            idempotency_key="correzione-troppo-breve",
            expected_status=PresidioStatus.NOTIFICATION_CONFIRMED,
        )

    repo.transition(
        presidio_id,
        PresidioStatus.NEEDS_REVIEW,
        actor="avvocato-test",
        reason="La conferma era stata selezionata per errore e richiede un nuovo esame.",
        evidence={
            "source": "ui_presidio",
            "operation": "decision_revision",
            "previous_decision": "NOTIFICATION_CONFIRMED",
            "target_decision": "NEEDS_REVIEW",
        },
        idempotency_key="correzione-decisione",
        expected_status=PresidioStatus.NOTIFICATION_CONFIRMED,
    )

    with repo.connection() as conn:
        transition = dict(conn.execute(
            """
            SELECT actor, reason, evidence_json, occurred_at
            FROM pec_legal_notification_transitions
            WHERE tenant_id=? AND presidio_id=? AND idempotency_key=?
            """,
            (repo.tenant_id, presidio_id, "correzione-decisione"),
        ).fetchone())
    assert transition["actor"] == "avvocato-test"
    assert transition["reason"].startswith("La conferma era stata selezionata")
    assert json.loads(transition["evidence_json"])["operation"] == "decision_revision"
    assert transition["occurred_at"].endswith("Z")
    assert repo.get_presidio(presidio_id)["status"] == PresidioStatus.NEEDS_REVIEW.value
    assert repo.verify_transition_chain(presidio_id)["ok"] is True


def test_repository_sqlite_schema_non_viene_riallineato_senza_lock_a_ogni_lettura() -> None:
    presidio_source = Path("pct/pec_notification_presidio/repository.py").read_text(encoding="utf-8")
    pec_source = Path("pct/pec_pipeline.py").read_text(encoding="utf-8")

    assert "_SQLITE_SCHEMA_LOCKS" in presidio_source
    assert "_SQLITE_SCHEMA_READY" in presidio_source
    assert "_sqlite_is_locked" in presidio_source
    assert "for delay in (0.0, 0.2, 0.5, 1.0)" in presidio_source

    assert "_PEC_AUDIT_SCHEMA_LOCKS" in pec_source
    assert "_PEC_AUDIT_SCHEMA_READY" in pec_source
    assert "_sqlite_is_busy" in pec_source
    assert "for delay in (0.0, 0.2, 0.5, 1.0)" in pec_source


def test_identita_semantica_pec_unifica_prove_documentali_della_stessa_sentenza(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    service = NotificationPresidioService(repo)
    payload = {
        "fascicolo_id": "FASC-001",
        "source_message_id": "pec-sentenza-unica",
        "source_order_or_event_id": "pec-sentenza-unica",
        "source_effective_at": "2026-07-20T10:00:00+02:00",
        "trigger_type": "STRATEGIC_NOTIFICATION_REVIEW",
        "notification_case": "judgment_to_notify_review",
        "notification_instance_document_key": "pec-sentenza-unica:FASC-001:judgment_to_notify_review",
        "rulepack_version": "pytest",
        "priority": "P1",
        "confidence": 0.9,
        "live_pec_operational_event": True,
        "recipients": [{"name": "Ministero dell'Istruzione", "role": "controparte"}],
    }
    first = service.create_candidate(
        {
            **payload,
            "documents": [{"content_sha256": "a" * 64, "original_filename": "sentenza.pdf"}],
        }
    )
    second = service.create_candidate(
        {
            **payload,
            "documents": [{"content_sha256": "b" * 64, "original_filename": "sentenza.pdf.zip"}],
        }
    )

    assert first["created"] is True
    assert second["created"] is False
    with repo.connection() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM pec_legal_notification_presidia WHERE tenant_id=?",
            (repo.tenant_id,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM pec_legal_notification_documents WHERE tenant_id=? AND presidio_id=?",
            (repo.tenant_id, first["id"]),
        ).fetchone()[0] == 2


def test_audit_riconcilia_duplicati_della_stessa_pec_e_stesso_documento(tmp_path: Path) -> None:
    db_path = tmp_path / "pec_audit.sqlite"
    repo = NotificationPresidioRepository(db_path, tenant_id="tenant-notifiche-test")
    service = NotificationPresidioService(repo)
    base = {
        "fascicolo_id": "FASC-001",
        "source_message_id": "pec-duplicata",
        "source_order_or_event_id": "pec-duplicata",
        "source_effective_at": "2026-07-20T10:00:00+02:00",
        "trigger_type": "STRATEGIC_NOTIFICATION_REVIEW",
        "notification_case": "judgment_to_notify_review",
        "rulepack_version": "pytest",
        "priority": "P1",
        "confidence": 0.9,
        "live_pec_operational_event": True,
        "documents": [{"content_sha256": "c" * 64, "original_filename": "sentenza.pdf"}],
    }
    first = service.create_candidate(
        {
            **base,
            "recipients": [{"name": "Ministero dell'Istruzione si dà atto", "role": "controparte"}],
        }
    )
    second = service.create_candidate(
        {
            **base,
            "recipients": [{"name": "Ministero dell'Istruzione", "role": "controparte"}],
        }
    )
    assert first["created"] is True
    assert second["created"] is True
    audit = PecAuditRepository(db_path, tenant_id="tenant-notifiche-test")

    report = audit.reconcile_duplicate_notification_presidia(message_id="pec-duplicata", actor="pytest")

    assert report["checked_groups"] == 1
    assert report["cancelled"] == 1
    assert len(report["cancelled_presidio_ids"]) == 1
    with repo.connection() as conn:
        statuses = [
            row[0]
            for row in conn.execute(
                "SELECT status FROM pec_legal_notification_presidia WHERE tenant_id=? ORDER BY status",
                (repo.tenant_id,),
            ).fetchall()
        ]
    assert statuses.count(PresidioStatus.CANCELLED.value) == 1
    assert len([status for status in statuses if status != PresidioStatus.CANCELLED.value]) == 1


def test_presidio_mixed_rdac_and_failure_stays_partial_with_p0(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    service = NotificationPresidioService(repo)
    reconciler = PecNotificationReconciler(repo)
    first = {
        "name": "Mario Rossi",
        "fiscal_id": "RSSMRA80A01H501U",
        "pec_address": "mario.rossi@pec.test",
        "role": "controparte",
    }
    second = {
        "name": "Anna Bianchi",
        "fiscal_id": "BNCNNA80A41H501Y",
        "pec_address": "anna.bianchi@pec.test",
        "role": "controparte",
    }
    presidio_id = _candidate(service, recipients=[first, second])

    _sent(reconciler, presidio_id=presidio_id, message_id="sent-mario", recipient=first)
    _sent(reconciler, presidio_id=presidio_id, message_id="sent-anna", recipient=second)
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.RDAC,
            message_id="rdac-mario",
            original_message_id="sent-mario",
            recipient_address=first["pec_address"],
            occurred_at="2026-07-20T10:40:00+02:00",
        )
    )
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.FAILURE,
            message_id="failure-anna",
            original_message_id="sent-anna",
            recipient_address=second["pec_address"],
            failure_reason="casella destinatario piena",
            failure_attribution="attributable_to_recipient",
            occurred_at="2026-07-20T10:45:00+02:00",
        )
    )

    presidio = repo.get_presidio(presidio_id)
    assert presidio["status"] == PresidioStatus.PARTIAL_DELIVERY.value
    assert presidio["priority"] == Priority.P0.value
    assert not bool(presidio["human_review_required"])
    rows = _recipient_rows(repo, presidio_id)
    assert [row["delivery_status"] for row in rows] == ["failed", "delivered"]
    assert rows[0]["failure_attribution"] == "attributable_to_recipient"


def test_uncertain_failure_requires_review_and_late_rdac_does_not_close(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    service = NotificationPresidioService(repo)
    reconciler = PecNotificationReconciler(repo)
    recipient = {
        "name": "Mario Rossi",
        "fiscal_id": "RSSMRA80A01H501U",
        "pec_address": "mario.rossi@pec.test",
        "role": "controparte",
    }
    presidio_id = _candidate(service, recipients=[recipient])

    _sent(reconciler, presidio_id=presidio_id, message_id="sent-mario", recipient=recipient)
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.FAILURE,
            message_id="failure-mario",
            original_message_id="sent-mario",
            recipient_address=recipient["pec_address"],
            failure_reason="errore consegna non attribuibile con certezza",
            failure_attribution="uncertain",
            occurred_at="2026-07-20T10:45:00+02:00",
        )
    )
    reconciler.process(
        NotificationReceiptEnvelope(
            kind=ReceiptKind.RDAC,
            message_id="rdac-tardiva",
            original_message_id="sent-mario",
            recipient_address=recipient["pec_address"],
            occurred_at="2026-07-20T10:55:00+02:00",
        )
    )

    presidio = repo.get_presidio(presidio_id)
    assert presidio["status"] == PresidioStatus.DELIVERY_FAILED.value
    assert presidio["priority"] == Priority.P0.value
    assert bool(presidio["human_review_required"])
    [row] = _recipient_rows(repo, presidio_id)
    assert row["delivery_status"] == "failed"
    assert row["failure_attribution"] == "uncertain"


def test_cutoff_storico_non_chiude_sentenza_pec_operativa_senza_prova() -> None:
    decision = classify_historical_record(
        {
            "notification_case": "judgment_to_notify_review",
            "live_pec_operational_event": True,
            "pec_official_delivery_at": "2026-07-16T13:01:03+02:00",
            "complete_proof": False,
        }
    )

    assert decision.status == PresidioStatus.DETECTED
    assert decision.legacy_assumed_handled is False
    assert decision.human_review_required is True


def test_richiesta_espressa_ante_cutoff_resta_operativa_senza_prova() -> None:
    decision = classify_historical_record(
        {
            "notification_case": "judgment_to_notify_review",
            "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
            "pec_official_delivery_at": "2026-07-16T13:01:03+02:00",
            "complete_proof": False,
        }
    )

    assert decision.status == PresidioStatus.DETECTED
    assert decision.legacy_assumed_handled is False


def test_termine_esplicito_dopo_cutoff_resta_attivo() -> None:
    decision = classify_historical_record(
        {
            "notification_case": "judgment_to_notify_review",
            "pec_official_delivery_at": "2026-07-16T13:01:03+02:00",
            "explicit_due_at": "2026-07-20T09:00:00+02:00",
            "complete_proof": False,
        }
    )

    assert decision.status == PresidioStatus.DETECTED
    assert decision.legacy_assumed_handled is False


def test_revisione_puo_registrare_storico_gestito_con_traccia_audit(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    service = NotificationPresidioService(repo)
    recipient = {
        "name": "Ministero dell'Istruzione e del Merito",
        "fiscal_id": "",
        "pec_address": "",
        "role": "controparte",
    }
    presidio_id = _candidate(service, recipients=[recipient])
    repo.transition(
        presidio_id,
        PresidioStatus.NEEDS_REVIEW,
        actor="pytest",
        reason="Verifica storica richiesta dallo studio.",
        evidence={"source": "audit"},
        idempotency_key="review-history",
    )
    repo.transition(
        presidio_id,
        PresidioStatus.LEGACY_ASSUMED_HANDLED,
        actor="pytest",
        reason="Dichiarazione dello studio registrata nell'audit storico.",
        evidence={"source": "tenant-declaration", "cutoff": "19/07/2026"},
        idempotency_key="legacy-history",
    )

    assert repo.get_presidio(presidio_id)["status"] == PresidioStatus.LEGACY_ASSUMED_HANDLED.value


def test_pipeline_materializza_sentenza_429_in_presidio_notifica(tmp_path: Path) -> None:
    audit = PecAuditRepository(tmp_path / "pec_audit.sqlite", tenant_id="tenant-notifiche-test")
    msg = EmailMessage()
    msg["Subject"] = "Tribunale Ordinario di Padova Notificazione ai sensi del D.L. 179/2012"
    msg["From"] = "Cancelleria <tribunale.padova@giustiziacert.it>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Mon, 20 Jul 2026 13:01:03 +0200"
    msg["Message-ID"] = "<sentenza-429-presidio@example.test>"
    msg.set_content(
        "SENTENZA A VERBALE (art. 127 ter cpc). Il Giudice decide la causa con sentenza "
        "a norma degli artt. 429 e 127ter cpc. Il Giudice, definitivamente decidendo, "
        "condanna il Ministero alle spese che liquida in € 1.030,00 con distrazione in favore "
        "del procuratore antistatario."
    )

    ingest = audit.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="1")
    audit.parse_and_store(ingest["id"], actor="pytest")
    with audit.connect() as conn:
        conn.execute(
            "UPDATE pec_messages SET linked_fascicolo_id=?, status=? WHERE tenant_id=? AND id=?",
            ("C3565650", "linked", audit.tenant_id, ingest["id"]),
        )

    result = audit.validate_message(ingest["id"], actor="pytest")
    assert result["notification_presidia"]["created"] == 1
    rerun = audit.validate_message(ingest["id"], actor="pytest-rerun")
    assert rerun["notification_presidia"]["created"] == 0

    with audit.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM pec_legal_notification_presidia WHERE tenant_id=?",
            (audit.tenant_id,),
        ).fetchone()[0] == 1
        presidio = conn.execute(
            "SELECT * FROM pec_legal_notification_presidia WHERE tenant_id=?",
            (audit.tenant_id,),
        ).fetchone()
        assert presidio is not None
        assert presidio["fascicolo_id"] == "C3565650"
        assert presidio["status"] == PresidioStatus.DETECTED.value
        assert presidio["notification_case"] == "judgment_to_notify_review"
        recipient = conn.execute(
            "SELECT * FROM pec_legal_notification_recipients WHERE tenant_id=? AND presidio_id=?",
            (audit.tenant_id, presidio["id"]),
        ).fetchone()
        assert recipient is not None
        assert recipient["name"] == "Destinatario da verificare"


def test_pipeline_importa_accettazione_e_consegna_notifica_in_fascicolo_e_presidio(tmp_path: Path) -> None:
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo

    tenant_id = "tenant-notifiche-test"
    audit_db = tmp_path / "pec_audit.sqlite"
    fascicoli_db = tmp_path / "fascicoli.json"
    fascicoli_docs = tmp_path / "documenti"
    fascicoli = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs))
    fascicolo = fascicoli.nuovo("Notifica PEC L. 53/1994", TipoFascicolo.CIVILE, numero_rg="203", anno_rg=2026)
    repo = NotificationPresidioRepository(audit_db, tenant_id=tenant_id)
    service = NotificationPresidioService(repo)
    recipient = {
        "name": "Avvocatura distrettuale di Stato di Milano",
        "role": "controparte",
        "pec_address": "ads.mi@mailcert.avvocaturastato.it",
        "fiscal_id": "97021490152",
    }
    presidio_id = str(service.create_candidate({
        "fascicolo_id": fascicolo.id,
        "source_message_id": "provvedimento-da-notificare",
        "source_effective_at": "2026-07-24T14:20:00+02:00",
        "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
        "notification_case": "decreto_fissazione",
        "rulepack_version": "pytest",
        "priority": "P1",
        "confidence": 1,
        "detection_reason": "Procedura notifica L. 53/1994 generata dal software.",
        "documents": [{"content_sha256": "a" * 64, "original_filename": "decreto.pdf"}],
        "recipients": [recipient],
    })["id"])
    sent_message_id = "<sent-notifica-jkobkrqc@example.test>"
    _sent(
        PecNotificationReconciler(repo),
        presidio_id=presidio_id,
        message_id=sent_message_id,
        recipient=recipient,
    )
    audit = PecAuditRepository(
        audit_db,
        tenant_id=tenant_id,
        fascicoli_db_path=fascicoli_db,
        fascicoli_docs_path=fascicoli_docs,
    )

    def _receipt(kind: str, message_id: str) -> str:
        label = "ACCETTAZIONE" if kind == "accettazione" else "CONSEGNA"
        msg = EmailMessage()
        msg["Subject"] = (
            f"{label}: Notificazione ai sensi della legge n. 53 - 1994 e succ. mod. "
            "[JQ203-L01] [Notifica_ID:JkObKrQc]"
        )
        msg["From"] = "postacert <postacert@pec.example.test>"
        msg["To"] = "studio@example.test"
        msg["Date"] = "Fri, 24 Jul 2026 14:31:00 +0200"
        msg["Message-ID"] = message_id
        msg["X-Riferimento-Message-ID"] = sent_message_id
        msg.set_content(f"Ricevuta di {kind} per la notificazione ai sensi della legge n. 53/1994.")
        msg.add_attachment(
            (
                "<postacert>"
                f"<tipo>{kind}</tipo>"
                "<msgid>sent-notifica-jkobkrqc@example.test</msgid>"
                "<destinatario>ads.mi@mailcert.avvocaturastato.it</destinatario>"
                "<data>2026-07-24T14:31:00+02:00</data>"
                "</postacert>"
            ),
            subtype="xml",
            filename="daticert.xml",
        )
        ingested = audit.ingest_mime(
            msg.as_bytes(policy=policy.SMTP),
            account_email="studio@example.test",
            folder="INBOX",
            imap_uid=message_id.strip("<>"),
        )
        audit.parse_and_store(ingested["id"], actor="pytest")
        result = audit.validate_message(ingested["id"], actor="pytest")
        assert result["notification_receipt_automation"]["matched"] is True
        assert result["notification_receipt_automation"]["fascicolo"]["ok"] is True
        return ingested["id"]

    rac_audit_id = _receipt("accettazione", "<rac-jkobkrqc@example.test>")
    rdac_audit_id = _receipt("avvenuta_consegna", "<rdac-jkobkrqc@example.test>")

    presidio = repo.get_presidio(presidio_id)
    assert presidio["status"] == PresidioStatus.DELIVERY_COMPLETE.value
    [recipient_row] = _recipient_rows(repo, presidio_id)
    assert recipient_row["sent_message_id"] == sent_message_id
    assert recipient_row["rac_message_id"] == "<rac-jkobkrqc@example.test>"
    assert recipient_row["rdac_message_id"] == "<rdac-jkobkrqc@example.test>"
    with repo.connection() as conn:
        roles = {
            row["document_role"]: row["fascicolo_document_id"]
            for row in conn.execute(
                """
                SELECT document_role, fascicolo_document_id
                FROM pec_legal_notification_documents
                WHERE tenant_id=? AND presidio_id=? AND document_role IN ('rac', 'rdac')
                """,
                (tenant_id, presidio_id),
            ).fetchall()
        }
    assert set(roles) == {"rac", "rdac"}
    saved = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs)).get(fascicolo.id)
    assert saved is not None
    assert sum("IUSENTRA_LEGAL_NOTIFICATION_RECEIPT" in doc.note for doc in saved.documenti) == 2
    assert sum("IUSENTRA_LEGAL_NOTIFICATION_RECEIPT" in activity.note for activity in saved.attivita) == 2
    assert any("receipt_kind: RAC" in doc.note for doc in saved.documenti)
    assert any("receipt_kind: RdAC" in doc.note for doc in saved.documenti)

    repeat = audit.validate_message(rdac_audit_id, actor="pytest-repeat")
    assert repeat["notification_receipt_automation"]["matched"] is True
    saved_repeat = GestioneFascicoli(str(fascicoli_db), documents_dir=str(fascicoli_docs)).get(fascicolo.id)
    assert saved_repeat is not None
    assert sum("IUSENTRA_LEGAL_NOTIFICATION_RECEIPT" in doc.note for doc in saved_repeat.documenti) == 2
    assert sum("IUSENTRA_LEGAL_NOTIFICATION_RECEIPT" in activity.note for activity in saved_repeat.attivita) == 2
    assert rac_audit_id != rdac_audit_id


def test_pipeline_chiude_sentenza_429_se_prova_notifica_gia_presente(tmp_path: Path) -> None:
    studio_db = tmp_path / "studio.db"
    with sqlite3.connect(str(studio_db)) as conn:
        conn.execute(
            """
            CREATE TABLE fascicoli (
                id TEXT PRIMARY KEY,
                documenti_json TEXT,
                attivita_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO fascicoli (id, documenti_json, attivita_json) VALUES (?, ?, ?)",
            (
                "C3565650",
                "[]",
                "[]",
            ),
        )

    audit = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="tenant-notifiche-test",
        fascicoli_db_path=studio_db,
    )
    msg = EmailMessage()
    msg["Subject"] = "Tribunale Ordinario di Padova Notificazione ai sensi del D.L. 179/2012"
    msg["From"] = "Cancelleria <tribunale.padova@giustiziacert.it>"
    msg["To"] = "studio@example.test"
    msg["Date"] = "Thu, 16 Jul 2026 13:01:03 +0200"
    msg["Message-ID"] = "<sentenza-429-presidio-proof@example.test>"
    msg.set_content(
        "SENTENZA A VERBALE (art. 127 ter cpc). Il Giudice decide la causa con sentenza "
        "a norma degli artt. 429 e 127ter cpc. Il Giudice, definitivamente decidendo, "
        "condanna il Ministero alle spese con distrazione in favore del procuratore antistatario."
    )

    ingest = audit.ingest_mime(msg.as_bytes(policy=policy.SMTP), account_email="studio@example.test", folder="INBOX", imap_uid="2")
    audit.parse_and_store(ingest["id"], actor="pytest")
    recipient_pec = "avvocatura.padova@avvocaturastato.it"
    notification_id = "notifica-sentenza-abc"
    sent_message_id = "notifica-sentenza-abc@pec.example.test"
    documents = [
        {
            "data_documento": "2026-07-16",
            "document_role": "notified_act",
            "notification_id": notification_id,
            "notified_source_message_id": ingest["id"],
        },
        {
            "data_documento": "2026-07-16",
            "document_role": "relata",
            "notification_id": notification_id,
            "notified_source_message_id": ingest["id"],
        },
    ]
    activities = [
        {
            "data": "2026-07-16",
            "event_type": "SENT_NOTIFICATION",
            "notification_id": notification_id,
            "message_id": sent_message_id,
            "recipient_pec": recipient_pec,
            "legal_basis": "Legge 53/1994",
        },
        {
            "data": "2026-07-16",
            "receipt_kind": "RAC",
            "notification_id": notification_id,
            "sent_message_id": sent_message_id,
        },
        {
            "data": "2026-07-16",
            "receipt_kind": "RdAC",
            "notification_id": notification_id,
            "sent_message_id": sent_message_id,
            "recipient_pec": recipient_pec,
        },
    ]
    with sqlite3.connect(str(studio_db)) as conn:
        conn.execute(
            "UPDATE fascicoli SET documenti_json=?, attivita_json=? WHERE id=?",
            (json.dumps(documents), json.dumps(activities), "C3565650"),
        )
    with audit.connect() as conn:
        conn.execute(
            "UPDATE pec_messages SET linked_fascicolo_id=?, status=? WHERE tenant_id=? AND id=?",
            ("C3565650", "linked", audit.tenant_id, ingest["id"]),
        )

    result = audit.validate_message(ingest["id"], actor="pytest")
    assert result["notification_presidia"]["created"] == 1

    with audit.connect() as conn:
        rows = conn.execute(
            "SELECT status, notification_case, resolution_code FROM pec_legal_notification_presidia WHERE tenant_id=?",
            (audit.tenant_id,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == PresidioStatus.CLOSED.value
        assert rows[0]["notification_case"] == "judgment_to_notify_review"
        assert rows[0]["resolution_code"] == "proof_already_present"


def test_due_notifiche_indipendenti_nello_stesso_fascicolo_non_chiudono_un_terzo_atto(tmp_path: Path) -> None:
    studio_db = tmp_path / "studio.db"

    def _chain(notification_id: str, act_message_id: str, recipient: str) -> tuple[list[dict], list[dict]]:
        sent_message_id = f"{notification_id}@pec.example.test"
        documents = [
            {
                "data_documento": "2026-07-17",
                "nome": f"Sentenza {notification_id}.pdf",
                "document_role": "notified_act",
                "notification_id": notification_id,
                "notified_source_message_id": act_message_id,
            },
            {
                "data_documento": "2026-07-17",
                "nome": f"Relata {notification_id}.pdf",
                "document_role": "relata",
                "notification_id": notification_id,
                "notified_source_message_id": act_message_id,
            },
        ]
        activities = [
            {
                "data": "2026-07-17",
                "titolo": "Notificazione ai sensi della Legge 53/1994",
                "event_type": "SENT_NOTIFICATION",
                "notification_id": notification_id,
                "message_id": sent_message_id,
                "recipient_pec": recipient,
                "legal_basis": "Legge 53/1994",
            },
            {
                "data": "2026-07-17",
                "receipt_kind": "RAC",
                "notification_id": notification_id,
                "sent_message_id": sent_message_id,
            },
            {
                "data": "2026-07-17",
                "titolo": "Ricevuta completa di avvenuta consegna",
                "receipt_kind": "RdAC",
                "notification_id": notification_id,
                "sent_message_id": sent_message_id,
                "recipient_pec": recipient,
            },
        ]
        return documents, activities

    documents_a, activities_a = _chain("notifica-a", "atto-c-corrente", "destinatario-a@example.test")
    documents_b, activities_b = _chain("notifica-b", "atto-c-corrente", "destinatario-b@example.test")
    with sqlite3.connect(str(studio_db)) as conn:
        conn.execute(
            """
            CREATE TABLE fascicoli (
                id TEXT PRIMARY KEY,
                documenti_json TEXT,
                attivita_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO fascicoli (id, documenti_json, attivita_json) VALUES (?, ?, ?)",
            (
                "FASC-DUE-NOTIFICHE",
                json.dumps([*documents_a, *documents_b]),
                json.dumps([*activities_a, *activities_b]),
            ),
        )

    audit = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="tenant-notifiche-test",
        fascicoli_db_path=studio_db,
    )
    proof = audit._notification_complete_proof_from_fascicolo(
        fascicolo_id="FASC-DUE-NOTIFICHE",
        source_effective_at="2026-07-16T13:01:03+02:00",
        source_message_id="atto-c-corrente",
        candidate_documents=[],
        candidate_recipients=[{"pec_address": "destinatario-c@example.test"}],
    )

    assert proof == {}


def test_stessa_notifica_due_destinatari_con_una_sola_rdac_resta_aperta(tmp_path: Path) -> None:
    studio_db = tmp_path / "studio.db"
    source_message_id = "atto-multi-destinatario"
    notification_id = "notifica-multi-destinatario"
    recipient_a = "destinatario-a@example.test"
    recipient_b = "destinatario-b@example.test"
    documents = [
        {
            "data_documento": "2026-07-17",
            "document_role": "notified_act",
            "notification_id": notification_id,
            "notified_source_message_id": source_message_id,
        },
        {
            "data_documento": "2026-07-17",
            "document_role": "relata",
            "notification_id": notification_id,
            "notified_source_message_id": source_message_id,
        },
    ]
    activities = [
        {
            "data": "2026-07-17",
            "event_type": "SENT_NOTIFICATION",
            "notification_id": notification_id,
            "message_id": "invio-a@example.test",
            "recipient_pec": recipient_a,
            "legal_basis": "Legge 53/1994",
        },
        {
            "data": "2026-07-17",
            "event_type": "SENT_NOTIFICATION",
            "notification_id": notification_id,
            "message_id": "invio-b@example.test",
            "recipient_pec": recipient_b,
            "legal_basis": "Legge 53/1994",
        },
        {
            "data": "2026-07-17",
            "receipt_kind": "RAC",
            "notification_id": notification_id,
            "sent_message_id": "invio-a@example.test",
        },
        {
            "data": "2026-07-17",
            "receipt_kind": "RAC",
            "notification_id": notification_id,
            "sent_message_id": "invio-b@example.test",
        },
        {
            "data": "2026-07-17",
            "receipt_kind": "RdAC",
            "notification_id": notification_id,
            "sent_message_id": "invio-a@example.test",
            "recipient_pec": recipient_a,
        },
    ]
    with sqlite3.connect(str(studio_db)) as conn:
        conn.execute(
            """
            CREATE TABLE fascicoli (
                id TEXT PRIMARY KEY,
                documenti_json TEXT,
                attivita_json TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO fascicoli (id, documenti_json, attivita_json) VALUES (?, ?, ?)",
            (
                "FASC-MULTI-DESTINATARIO",
                json.dumps(documents),
                json.dumps(activities),
            ),
        )

    audit = PecAuditRepository(
        tmp_path / "pec_audit.sqlite",
        tenant_id="tenant-notifiche-test",
        fascicoli_db_path=studio_db,
    )
    proof = audit._notification_complete_proof_from_fascicolo(
        fascicolo_id="FASC-MULTI-DESTINATARIO",
        source_effective_at="2026-07-16T13:01:03+02:00",
        source_message_id=source_message_id,
        candidate_documents=[],
        candidate_recipients=[
            {"pec_address": recipient_a},
            {"pec_address": recipient_b},
        ],
    )
    decision = classify_historical_record(
        {
            "source_effective_at": "2026-07-16T13:01:03+02:00",
            "live_pec_operational_event": True,
            "trigger_type": "EXPLICIT_NOTIFICATION_ORDER",
            "notification_case": "judgment_to_notify_review",
            "complete_proof": bool(proof),
        }
    )

    assert proof == {}
    assert decision.status == PresidioStatus.DETECTED
