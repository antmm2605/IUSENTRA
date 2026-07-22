from __future__ import annotations

import hashlib
import inspect
from email import policy
from email.message import EmailMessage
from pathlib import Path

import pytest

from pct.pec_pipeline import PecAuditRepository


def _same_mime() -> tuple[bytes, str]:
    header_message_id = "<pec-condivisa-tra-tenant@example.test>"
    message = EmailMessage()
    message["Subject"] = "Comunicazione di cancelleria RG 100/2026"
    message["From"] = "Cancelleria <tribunale@example.test>"
    message["To"] = "studio@example.test"
    message["Date"] = "Wed, 22 Jul 2026 09:30:00 +0200"
    message["Message-ID"] = header_message_id
    message.set_content("Testo PEC identico acquisito da due tenant distinti.")
    return message.as_bytes(policy=policy.SMTP), header_message_id


def test_stesso_mime_nello_stesso_audit_db_resta_distinto_per_tenant(tmp_path: Path) -> None:
    db_path = tmp_path / "pec-audit-condiviso.sqlite"
    tenant_a = PecAuditRepository(db_path, tenant_id="studio-a")
    tenant_b = PecAuditRepository(db_path, tenant_id="studio-b")
    raw_mime, header_message_id = _same_mime()

    first_a = tenant_a.ingest_mime(
        raw_mime,
        account_email="studio@example.test",
        enqueue=False,
    )
    first_b = tenant_b.ingest_mime(
        raw_mime,
        account_email="studio@example.test",
        enqueue=False,
    )

    assert first_a["duplicate"] is False
    assert first_b["duplicate"] is False
    assert first_a["id"] != first_b["id"]
    assert first_a["id"].startswith("pec_") and len(first_a["id"]) == 68
    assert first_b["id"].startswith("pec_") and len(first_b["id"]) == 68

    with tenant_a.connect() as conn:
        rows = conn.execute(
            "SELECT id, tenant_id, mime_sha256 FROM pec_messages ORDER BY tenant_id"
        ).fetchall()
    assert [(row["id"], row["tenant_id"]) for row in rows] == [
        (first_a["id"], "studio-a"),
        (first_b["id"], "studio-b"),
    ]
    assert rows[0]["mime_sha256"] == rows[1]["mime_sha256"]

    duplicate_a = tenant_a.ingest_mime(raw_mime, account_email="studio@example.test", enqueue=False)
    duplicate_b = tenant_b.ingest_mime(raw_mime, account_email="studio@example.test", enqueue=False)
    assert duplicate_a["id"] == first_a["id"] and duplicate_a["duplicate"] is True
    assert duplicate_b["id"] == first_b["id"] and duplicate_b["duplicate"] is True

    with tenant_a.connect() as conn:
        assert tenant_a.get_message_row(conn, first_a["id"])["tenant_id"] == "studio-a"
        with pytest.raises(KeyError, match="PEC non trovata"):
            tenant_a.get_message_row(conn, first_b["id"])
    with tenant_b.connect() as conn:
        assert tenant_b.get_message_row(conn, first_b["id"])["tenant_id"] == "studio-b"
        with pytest.raises(KeyError, match="PEC non trovata"):
            tenant_b.get_message_row(conn, first_a["id"])

    assert tenant_a.ids_by_header_message_ids([header_message_id]) == {
        header_message_id: first_a["id"]
    }
    assert tenant_b.ids_by_header_message_ids([header_message_id]) == {
        header_message_id: first_b["id"]
    }

    with tenant_a.connect() as conn:
        owners = {
            str(row["id"]): str(row["tenant_id"])
            for row in conn.execute("SELECT id, tenant_id FROM pec_messages").fetchall()
        }
    assert owners == {first_a["id"]: "studio-a", first_b["id"]: "studio-b"}


def test_record_legacy_resta_accessibile_solo_al_tenant_proprietario(tmp_path: Path) -> None:
    db_path = tmp_path / "pec-audit-legacy.sqlite"
    tenant_a = PecAuditRepository(db_path, tenant_id="studio-a")
    tenant_b = PecAuditRepository(db_path, tenant_id="studio-b")
    raw_mime, header_message_id = _same_mime()
    first_a = tenant_a.ingest_mime(raw_mime, account_email="studio@example.test", enqueue=False)
    legacy_id = f"pec_{hashlib.sha256(raw_mime).hexdigest()[:24]}"

    with tenant_a.connect() as conn:
        conn.execute(
            "UPDATE pec_messages SET id=? WHERE tenant_id=? AND id=?",
            (legacy_id, "studio-a", first_a["id"]),
        )

    duplicate_a = tenant_a.ingest_mime(raw_mime, account_email="studio@example.test", enqueue=False)
    first_b = tenant_b.ingest_mime(raw_mime, account_email="studio@example.test", enqueue=False)

    assert duplicate_a["duplicate"] is True
    assert duplicate_a["id"] == legacy_id
    assert first_b["duplicate"] is False
    assert first_b["id"] != legacy_id
    assert tenant_a.ids_by_header_message_ids([header_message_id]) == {header_message_id: legacy_id}
    assert tenant_b.ids_by_header_message_ids([header_message_id]) == {
        header_message_id: first_b["id"]
    }

    with tenant_a.connect() as conn:
        assert tenant_a.get_message_row(conn, legacy_id)["tenant_id"] == "studio-a"
    with tenant_b.connect() as conn:
        with pytest.raises(KeyError, match="PEC non trovata"):
            tenant_b.get_message_row(conn, legacy_id)

    with tenant_a.connect() as conn:
        owner = conn.execute(
            "SELECT tenant_id FROM pec_messages WHERE id=?",
            (legacy_id,),
        ).fetchone()
    assert owner is not None and owner["tenant_id"] == "studio-a"


def test_i_tre_percorsi_pec_non_contengono_fallback_cross_tenant() -> None:
    repository_source = inspect.getsource(PecAuditRepository)
    ingest_source = inspect.getsource(PecAuditRepository.ingest_mime)
    get_source = inspect.getsource(PecAuditRepository.get_message_row)
    ids_source = inspect.getsource(PecAuditRepository.ids_by_header_message_ids)

    assert "_tenant_scoped_message_id(self.tenant_id, mime_hash)" in ingest_source
    assert "stale_existing" not in ingest_source
    assert "UPDATE pec_messages SET tenant_id" not in ingest_source
    assert "SELECT * FROM pec_messages WHERE id=?" not in get_source
    assert "UPDATE pec_messages SET tenant_id" not in get_source
    assert "WHERE tenant_id=? AND message_id_header IN" in ids_source
    assert "ORDER BY CASE WHEN tenant_id" not in ids_source
    assert "_adopt_legacy_default_tenant_rows" not in repository_source
    assert "pec.tenant.legacy_default_adopted" not in repository_source


def test_schema_sqlite_e_postgres_mantengono_chiavi_uniche_per_tenant() -> None:
    sqlite_schema = Path("pct/sql/20260521_pec_audit_pipeline.sql").read_text(encoding="utf-8")
    postgres_schema = Path("pct/sql/20260521_pec_audit_pipeline_postgres.sql").read_text(encoding="utf-8")

    for schema in (sqlite_schema, postgres_schema):
        assert "UNIQUE (tenant_id, mime_sha256)" in schema
        assert "UNIQUE (tenant_id, account_email, message_id_header, mime_sha256)" in schema
        assert "idx_pec_messages_header ON pec_messages(tenant_id, message_id_header)" in schema
