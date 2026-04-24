"""Repository SQL leggero per metadati SIGP locali."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SQLITE_SCHEMA = Path(__file__).resolve().parents[2] / "pct" / "sql" / "20260424_sigp_repository.sql"


class SigpRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SQLITE_SCHEMA.read_text(encoding="utf-8"))
            conn.commit()

    def list_schema_versions(self) -> list[dict]:
        self.ensure_schema()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT version, descrizione, path_locale, main_xsd, attivo, data_pubblicazione, fonte "
                "FROM sigp_schema_versions ORDER BY attivo DESC, version DESC"
            ).fetchall()
        return [dict(row) for row in rows]
