from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from pct.client_portal import (
    CLIENT_PORTAL_TABLES,
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
