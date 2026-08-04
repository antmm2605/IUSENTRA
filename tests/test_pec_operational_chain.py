from __future__ import annotations

import json
import sqlite3
from inspect import signature
from pathlib import Path
from types import SimpleNamespace

from pct.pec_control_tower import PecControlTowerRepository
from pct.pec_pipeline import PecAuditRepository
from pct.tenant import GestioneTenant
from scripts.audit_pec_operational_chain import _email_relevant_for_pec, _report_has_127_false_remote
from scripts.audit_pec_operational_chain import run_audit as run_pec_operational_audit
from scripts.presidia_pec_local_archive import _email_relevant_for_pec as archive_email_relevant_for_pec
from scripts.presidia_pec_local_archive import presidia_studio
from web.services.pec_source_links import (
    _audit_message_id_for_control_row,
    control_tower_source_key,
    latest_control_tower_sources,
)


class _Email:
    def __init__(self, **values: object) -> None:
        for key, value in values.items():
            setattr(self, key, value)


def test_only_pec_evidence_marks_a_local_email_as_pec_relevant() -> None:
    ordinary = {
        "id": "ordinary",
        "message_id": "<ordinary@example.test>",
        "oggetto": "Documenti integrativi",
        "mittente": "studio@example.test",
        "origine": "INVIATI",
        "stato_pct": "",
        "allegati": [],
    }
    pec = {**ordinary, "id": "pec", "oggetto": "POSTA CERTIFICATA: COMUNICAZIONE 1428/2026/LAV"}
    assert not _email_relevant_for_pec(ordinary)
    assert _email_relevant_for_pec(pec)
    assert not archive_email_relevant_for_pec(_Email(**ordinary))
    assert archive_email_relevant_for_pec(_Email(**pec))


def test_remote_127_audit_ignores_written_hearing_and_detects_decisory_misclassification() -> None:
    written_hearing = {
        "remote_hearing": {"detected": False, "pdf_required": True, "links": []},
        "procedural_profile": {"evento_pec": "comunicazione_cancelleria", "messaggio_operativo": "Trattazione scritta"},
        "deadline_proposal": {"auto_create": True, "due_date": "2026-09-14"},
    }
    decisory_misclassification = {
        "remote_hearing": {"detected": True, "links": [{"url": "https://example.test/hearing"}]},
        "procedural_profile": {"messaggio_operativo": "Sentenza a verbale resa ai sensi dell'art. 127-ter c.p.c."},
        "deadline_proposal": {"auto_create": False, "due_date": ""},
    }
    assert not _report_has_127_false_remote(written_hearing)
    assert _report_has_127_false_remote(decisory_misclassification)


def test_full_control_tower_backfill_is_opt_in_for_ordinary_pec_presidio() -> None:
    assert signature(presidia_studio).parameters["control_tower_backfill"].default is False


def test_tenant_registry_mancante_viene_recuperato_da_storage_sqlite(tmp_path: Path) -> None:
    tenant_root = tmp_path / "tenants" / "tenant-8bf98719c459"
    (tenant_root / "config").mkdir(parents=True)
    sqlite3.connect(tenant_root / "studio.db").close()
    (tenant_root / "config" / "storage.json").write_text(
        json.dumps(
            {
                "slug": "studio-montagnese",
                "selected_mode": "SQLITE",
                "connessione_ok": True,
                "core_runtime_enabled": True,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (tenant_root / "config" / "studio.json").write_text(
        json.dumps(
            {
                "studio": {
                    "nome": "Studio Legale Montagnese",
                    "avvocato": "Avv. Giuseppe Montagnese",
                    "email": "studio@example.test",
                },
                "pec": {"indirizzo": "studio@pec.example.test"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = GestioneTenant(str(tmp_path / "tenants.json"))
    studi = manager.lista()

    assert (tmp_path / "tenants.json").exists()
    assert [studio.slug for studio in studi] == ["studio-montagnese"]
    assert studi[0].id == "tenant-local-studio-montagnese"
    assert studi[0].storage_key == "tenant-8bf98719c459"
    assert studi[0].db_mode == "SQLITE"
    assert "pec" in studi[0].moduli_attivi
    studio_db = manager.percorsi_dati("studio-montagnese", reconcile_aliases=False)["STUDIO_DB"].replace("\\", "/")
    assert studio_db.endswith("tenant-8bf98719c459/studio.db")


def test_audit_catena_pec_non_torna_verde_senza_studi(tmp_path: Path) -> None:
    result = run_pec_operational_audit(registry=tmp_path / "tenants.json")

    assert result["ok"] is False
    assert result["studios"] == {}
    assert "Nessuno studio attivo" in result["errors"][0]


def _insert_control_tower_source(
    repository: PecControlTowerRepository,
    *,
    communication_id: str,
    message_id_header: str,
    mime_sha256: str,
    received_at: str,
) -> None:
    with repository._connect() as connection:
        connection.execute(
            """
            INSERT INTO legal_communications
            (id, tenant_id, direction, account_email, folder, message_id_header, original_message_id,
             subject, sender, recipients_json, received_at, sent_at, mime_sha256, technical_type,
             legal_category, legal_event_type, confidence, confidence_label, requires_human_confirmation,
             status, fascicolo_id, fascicolo_score, risk_level, summary, extracted_json, evidence_json,
             source_json, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                communication_id,
                "studio-test",
                "inbound",
                "studio@pec.example.it",
                "INBOX",
                message_id_header,
                "",
                "ACCETTAZIONE: notifica",
                "posta-certificata@pec.example.it",
                "[]",
                received_at,
                "",
                mime_sha256,
                "PEC_RECEIPT_ACCEPTANCE",
                "PEC_OUTBOUND_PROOF",
                "ricevuta_accettazione_da_presidiare",
                0.99,
                "alta",
                0,
                "open",
                "FASC-1",
                1.0,
                "media",
                "Ricevuta PEC",
                "{}",
                "{}",
                "{}",
                received_at,
                received_at,
            ),
        )


def test_fallback_control_tower_non_sceglie_una_pec_se_tipo_e_secondo_sono_ambigui(tmp_path) -> None:
    audit_db = tmp_path / "email" / "pec_audit.sqlite"
    audit = PecAuditRepository(audit_db, tenant_id="studio-test")
    received_at = "2026-07-21T10:00:00+02:00"
    raw_a = (
        b"From: posta-certificata@pec.example.it\r\n"
        b"To: studio@pec.example.it\r\n"
        b"Date: Tue, 21 Jul 2026 10:00:00 +0200\r\n"
        b"Message-ID: <ricevuta-a@pec.example.it>\r\n"
        b"Subject: ACCETTAZIONE: notifica A\r\n\r\nRicevuta A"
    )
    raw_b = (
        b"From: posta-certificata@pec.example.it\r\n"
        b"To: studio@pec.example.it\r\n"
        b"Date: Tue, 21 Jul 2026 10:00:00 +0200\r\n"
        b"Message-ID: <ricevuta-b@pec.example.it>\r\n"
        b"Subject: ACCETTAZIONE: notifica B\r\n\r\nRicevuta B"
    )
    ingested_a = audit.ingest_mime(raw_a, enqueue=False)
    ingested_b = audit.ingest_mime(raw_b, enqueue=False)
    tower = PecControlTowerRepository(audit_db.with_name("pec_control_tower.sqlite"), tenant_id="studio-test")
    item = SimpleNamespace(
        source_event_type="ricevuta_accettazione_da_presidiare",
        source_event_at=received_at,
        data_decorrenza="",
    )
    key = control_tower_source_key(item)

    _insert_control_tower_source(
        tower,
        communication_id="comm-a",
        message_id_header="<ricevuta-a@pec.example.it>",
        mime_sha256=str(ingested_a["mime_sha256"]),
        received_at=received_at,
    )
    unique = latest_control_tower_sources([item], pec_audit_db=str(audit_db), tenant_id="studio-test")
    assert unique[key]["pecAuditId"] == ingested_a["id"]

    _insert_control_tower_source(
        tower,
        communication_id="comm-b",
        message_id_header="<ricevuta-b@pec.example.it>",
        mime_sha256=str(ingested_b["mime_sha256"]),
        received_at=received_at,
    )
    ambiguous = latest_control_tower_sources([item], pec_audit_db=str(audit_db), tenant_id="studio-test")
    assert key not in ambiguous

    exact_a = SimpleNamespace(
        note="PEC_CONTROL_TOWER:comm-a\nPresidio PEC da confermare.",
        source_event_type="ricevuta_accettazione_da_presidiare",
        source_event_at=received_at,
        data_decorrenza="",
    )
    exact_b = SimpleNamespace(
        note="PEC_CONTROL_TOWER:comm-b\nPresidio PEC da confermare.",
        source_event_type="ricevuta_accettazione_da_presidiare",
        source_event_at=received_at,
        data_decorrenza="",
    )
    exact = latest_control_tower_sources([exact_a, exact_b], pec_audit_db=str(audit_db), tenant_id="studio-test")
    assert exact[control_tower_source_key(exact_a)]["pecAuditId"] == ingested_a["id"]
    assert exact[control_tower_source_key(exact_b)]["pecAuditId"] == ingested_b["id"]


def test_fallback_oggetto_e_secondo_non_sceglie_un_audit_pec_ambiguo() -> None:
    audit = sqlite3.connect(":memory:")
    audit.row_factory = sqlite3.Row
    audit.execute(
        """
        CREATE TABLE pec_messages (
            id TEXT,
            tenant_id TEXT,
            mime_sha256 TEXT,
            message_id_header TEXT,
            received_at TEXT,
            metadata_json TEXT
        )
        """
    )
    for message_id in ("pec-a", "pec-b"):
        audit.execute(
            "INSERT INTO pec_messages VALUES (?, ?, ?, ?, ?, ?)",
            (
                message_id,
                "studio-test",
                f"hash-{message_id}",
                f"<{message_id}@pec.example.it>",
                "2026-07-21T10:00:00Z",
                '{"subject":"ACCETTAZIONE: notifica condivisa"}',
            ),
        )
    control = sqlite3.connect(":memory:")
    control.row_factory = sqlite3.Row
    control.execute(
        "CREATE TABLE source (mime_sha256 TEXT, message_id_header TEXT, subject TEXT, received_at TEXT)"
    )
    row = control.execute(
        "INSERT INTO source VALUES (?, ?, ?, ?) RETURNING *",
        (
            "hash-non-presente",
            "<header-non-presente@pec.example.it>",
            "ACCETTAZIONE: notifica condivisa",
            "2026-07-21T10:00:00+00:00",
        ),
    ).fetchone()

    assert row is not None
    assert _audit_message_id_for_control_row(row, audit, tenant_id="studio-test") == ""

    control.close()
    audit.close()
