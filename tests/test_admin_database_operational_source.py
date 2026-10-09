"""Guardrail: a mirror or backup must never attest active SQL availability."""
from __future__ import annotations

import pytest

from web.services.react_admin_database_bridge import DIRECT_JSON_MODULES, _date_label, build_react_admin_database_payload


class DatabaseSnapshot:
    MODULI_SQLITE_TABELLE = {"clienti": ("clienti", "id")}

    def __init__(self, *, operational: bool, table_error: bool = False):
        self.operational = operational
        self.table_error = table_error

    def statistiche(self):
        return {"moduli": [{"nome": "clienti", "record_totali": 265, "stato": "OK"}]}

    def analisi_uso(self):
        return {}

    def statistiche_sqlite(self, path):
        if path == "active.db" and not self.operational:
            return None
        return {"esiste": True, "tabelle": {"clienti": 267}, "errori_tabelle": {"clienti": "lettura fallita"} if self.table_error else {}}


@pytest.mark.parametrize("operational,table_error,verified", [(True, False, True), (False, False, False), (True, True, False)])
def test_active_sql_proof_cannot_come_from_mirror_snapshot_or_failed_count(operational, table_error, verified):
    database = DatabaseSnapshot(operational=operational, table_error=table_error)
    payload = build_react_admin_database_payload(
        lambda: database, lambda _: "backup.db", backup_dir="backups", studio_db_path="active.db",
        storage_runtime={"effective_mode": "SQLITE"},
    )
    module = payload["modules"][0]
    assert module["records"] == 265
    assert module["status"]["code"] == "OK"
    assert module["operational"]["verified"] is verified
    assert module["operational"]["records"] == (267 if verified else None)
    assert payload["sqlite"]["role"] == ("operativo" if operational else "snapshot")


@pytest.mark.parametrize("name", sorted(DIRECT_JSON_MODULES))
def test_sql_studio_does_not_hide_file_backed_operational_modules(name):
    database = DatabaseSnapshot(operational=True)
    database.statistiche = lambda: {"moduli": [{"nome": name, "record_totali": 7, "stato": "OK"}]}
    payload = build_react_admin_database_payload(
        lambda: database, lambda _: "backup.db", backup_dir="backups", studio_db_path="active.db",
        storage_runtime={"effective_mode": "SQLITE"},
    )
    module = payload["modules"][0]
    assert module["mirror"] is False
    assert module["kind"]["label"] == "File operativo"
    assert module["records"] == 7
    assert module["operational"]["verified"] is False
    assert "da adeguare" in module["operational"]["message"]


def test_visible_timestamp_uses_rome_and_never_exposes_invalid_raw_input():
    assert _date_label("2026-10-08T17:15:00Z") == "08/10/2026 19:15"
    assert _date_label("2026-01-08T17:15:00Z") == "08/01/2026 18:15"
    assert _date_label("2026-10-08") == "08/10/2026"
    assert _date_label("unparseable-timestamp") == "n.d."
