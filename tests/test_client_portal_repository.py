from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from pct.client_portal import (
    CLIENT_PORTAL_TABLES,
    ClientPortalError,
    ClientPortalRepository,
    SCHEMA_CLIENT_PORTAL_POSTGRES,
    SCHEMA_CLIENT_PORTAL_SQLITE,
    token_hash,
)


def _tables_from_sql(sql: str) -> set[str]:
    return set(re.findall(r"CREATE TABLE IF NOT EXISTS\s+([a-z0-9_]+)", sql, flags=re.I))


def test_client_portal_sqlite_postgres_schema_parity():
    sqlite_tables = _tables_from_sql(SCHEMA_CLIENT_PORTAL_SQLITE.read_text(encoding="utf-8"))
    postgres_tables = _tables_from_sql(SCHEMA_CLIENT_PORTAL_POSTGRES.read_text(encoding="utf-8"))

    assert sqlite_tables == postgres_tables == set(CLIENT_PORTAL_TABLES)
    assert "client_portal_invites" in sqlite_tables
    assert "token_hash TEXT NOT NULL" in SCHEMA_CLIENT_PORTAL_SQLITE.read_text(encoding="utf-8")
    assert "token_hash TEXT NOT NULL" in SCHEMA_CLIENT_PORTAL_POSTGRES.read_text(encoding="utf-8")


def test_client_portal_repository_crea_schema_e_salva_solo_hash_token(tmp_path: Path):
    repo = ClientPortalRepository(tmp_path / "client_portal.db")
    tenant_id = "studio-test"
    profile = repo.ensure_profile(
        tenant_id,
        client_id="CLI1",
        display_name="Mario Rossi",
        email="mario.rossi@example.it",
    )
    matter = repo.ensure_matter(
        tenant_id,
        client_id="CLI1",
        fascicolo_id="FASC1",
        title="Pratica contrattuale",
    )
    token = "token-cliente-non-salvato"
    created = repo.create_invite(
        tenant_id,
        client_id=profile["client_id"],
        matter_id=matter["id"],
        token_value=token,
    )

    assert repo.schema_table_names() == set(CLIENT_PORTAL_TABLES)
    assert created["invite"]["token_hash"] == token_hash(token)
    assert created["token"] == token

    raw_db = (tmp_path / "client_portal.db").read_bytes()
    assert token.encode("utf-8") not in raw_db
    with sqlite3.connect(tmp_path / "client_portal.db") as conn:
        rows = conn.execute("SELECT token_hash FROM client_portal_invites").fetchall()
    assert rows == [(token_hash(token),)]


def test_client_portal_snapshot_is_tenant_scoped(tmp_path: Path):
    repo = ClientPortalRepository(tmp_path / "client_portal.db")
    repo.ensure_profile("studio-a", client_id="CLI1", display_name="Cliente A")
    matter_a = repo.ensure_matter("studio-a", client_id="CLI1", fascicolo_id="FASC1", title="Pratica A")
    repo.create_invite("studio-a", client_id="CLI1", matter_id=matter_a["id"], token_value="token-a")

    repo.ensure_profile("studio-b", client_id="CLI1", display_name="Cliente B")
    matter_b = repo.ensure_matter("studio-b", client_id="CLI1", fascicolo_id="FASC1", title="Pratica B")
    repo.create_invite("studio-b", client_id="CLI1", matter_id=matter_b["id"], token_value="token-b")

    snap_a = repo.dashboard_snapshot("studio-a")
    snap_b = repo.dashboard_snapshot("studio-b")

    assert [row["title"] for row in snap_a["matters"]] == ["Pratica A"]
    assert [row["title"] for row in snap_b["matters"]] == ["Pratica B"]


def test_client_portal_appointment_update_records_client_actor(tmp_path: Path):
    repo = ClientPortalRepository(tmp_path / "client_portal.db")
    repo.ensure_profile("studio-a", client_id="CLI1", display_name="Cliente A")
    matter = repo.ensure_matter("studio-a", client_id="CLI1", fascicolo_id="FASC1", title="Pratica A")
    appointment = repo.add_appointment(
        "studio-a",
        matter_id=matter["id"],
        title="Colloquio",
        starts_at="2026-06-08T10:00:00Z",
    )

    updated = repo.update_appointment_status(
        "studio-a",
        appointment["id"],
        status="confermato",
        actor_id="CLI1",
        actor_type="cliente",
    )

    assert updated["status"] == "confermato"
    with sqlite3.connect(tmp_path / "client_portal.db") as conn:
        row = conn.execute(
            "SELECT actor_type, actor_id, action FROM client_portal_audit_events WHERE resource_id = ?",
            (appointment["id"],),
        ).fetchone()
    assert row == ("cliente", "CLI1", "client_portal.appointment.update")


def _seed_document(repo: ClientPortalRepository, tenant_id: str, *, status: str = "caricato") -> dict:
    repo.ensure_profile(tenant_id, client_id="CLI1", display_name="Cliente A")
    matter = repo.ensure_matter(tenant_id, client_id="CLI1", fascicolo_id="FASC1", title="Pratica A")
    return repo.add_document(
        tenant_id,
        matter_id=matter["id"],
        request_id="documento-identita",
        client_id="CLI1",
        filename="carta.pdf",
        stored_name=f"{matter['id']}/x_carta.pdf",
        content_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
        status=status,
    )


def test_client_portal_document_status_e_revisione(tmp_path: Path):
    repo = ClientPortalRepository(tmp_path / "client_portal.db")
    document = _seed_document(repo, "studio-a", status="in_revisione")

    assert document["status"] == "in_revisione"
    found = repo.find_documents_by_request(
        "studio-a", matter_id=document["matter_id"], request_id="documento-identita"
    )
    assert [row["id"] for row in found] == [document["id"]]
    assert repo.find_documents_by_request("studio-b", matter_id=document["matter_id"], request_id="documento-identita") == []

    reviewed = repo.update_document_status(
        "studio-a",
        document["id"],
        status="approvato",
        reviewed_at="2026-07-10T10:00:00+00:00",
        review_note="Documento leggibile.",
        actor_id="op1",
    )
    assert reviewed["status"] == "approvato"
    assert reviewed["reviewed_at"] == "2026-07-10T10:00:00+00:00"
    assert reviewed["review_note"] == "Documento leggibile."

    with pytest.raises(ClientPortalError):
        repo.update_document_status("studio-a", document["id"], status="stato-inventato")


def test_client_portal_documento_firmato_definitivo_immutabile(tmp_path: Path):
    repo = ClientPortalRepository(tmp_path / "client_portal.db")
    document = _seed_document(repo, "studio-a", status="firmato_definitivo")

    with pytest.raises(ClientPortalError):
        repo.update_document_status("studio-a", document["id"], status="sostituito")

    with pytest.raises(ClientPortalError):
        repo.add_document(
            "studio-a",
            matter_id=document["matter_id"],
            request_id="x",
            client_id="CLI1",
            filename="f.pdf",
            stored_name="m/f.pdf",
            content_type="application/pdf",
            size_bytes=1,
            sha256="b" * 64,
            status="stato-non-valido",
        )
