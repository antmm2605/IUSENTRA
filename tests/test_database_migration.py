from __future__ import annotations

import json
import sqlite3

from core.database import sqlite_path_from_url
from core.storage.migration_service import migrate_json_directory_to_sqlite


def test_json_migration_is_idempotent_and_creates_fts(tmp_path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "clienti.json").write_text(
        json.dumps([{"id": "c1", "nome": "Mario Rossi", "codice_fiscale": "RSSMRA80A01H501Z"}]),
        encoding="utf-8",
    )
    database_url = f"sqlite:///{tmp_path / 'iusentra.sqlite'}"

    first = migrate_json_directory_to_sqlite(data_root, database_url)
    second = migrate_json_directory_to_sqlite(data_root, database_url)

    assert first["ok"]
    assert second["ok"]
    assert first["records"] == second["records"] == 1

    db_path = sqlite_path_from_url(database_url)
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM json_documents").fetchone()[0]
        rows = conn.execute("SELECT title FROM json_documents_fts WHERE json_documents_fts MATCH 'Mario'").fetchall()
    assert count == 1
    assert rows


def test_json_migration_reports_corrupt_file(tmp_path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "rotto.json").write_text("{", encoding="utf-8")

    report = migrate_json_directory_to_sqlite(data_root, f"sqlite:///{tmp_path / 'iusentra.sqlite'}")

    assert not report["ok"]
    assert report["errors"]
