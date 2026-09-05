"""SQL directory for public mediation organisms and source-backed site checks.

Registry imports are explicit jobs, never a side effect of opening a page.
The ministerial snapshot is bootstrap input, not runtime source of truth.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from pct.postgres_runtime_support import PostgresRepositoryBackend

SCHEMA = Path(__file__).with_name("sql") / "20260905_mediazione_directory.sql"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MediazioneDirectoryRepository:
    def __init__(self, db_path: str | Path, *, postgres_dsn: str = "") -> None:
        self.db_path = Path(db_path)
        self.backend = PostgresRepositoryBackend(postgres_dsn, SCHEMA) if postgres_dsn else None
        if not self.backend:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with self.connection() as conn:
                conn.executescript(SCHEMA.read_text(encoding="utf-8"))

    @property
    def source_of_truth(self) -> str:
        return "postgresql" if self.backend else "sqlite"

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self.backend:
            try:
                with self.backend.connection() as conn:
                    yield conn
            finally:
                self.backend.close()
        else:
            conn = sqlite3.connect(self.db_path, timeout=20)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            try:
                with conn:
                    yield conn
            finally:
                conn.close()

    def import_registry(self, rows: list[dict], *, source: str, checked_at: str) -> int:
        if not source or not checked_at:
            raise ValueError("Fonte e data del registro sono obbligatorie.")
        organisms = [r for r in rows if r.get("registry_kind") == "organismo"]
        if not organisms:
            raise ValueError("Il registro non contiene organismi di mediazione.")
        seen = set()
        for row in organisms:
            number = str(row.get("registration_number") or "").strip()
            if not number or not str(row.get("name") or "").strip() or number in seen:
                raise ValueError("Registro incompleto o numero di iscrizione duplicato.")
            seen.add(number)
        with self.connection() as conn:
            for row in organisms:
                number = str(row["registration_number"]).strip()
                previous = conn.execute(
                    "SELECT website FROM mediazione_organismi WHERE registration_number=?", (number,)
                ).fetchone()
                website = str(row.get("website") or "").strip()
                if previous and previous["website"] != website:
                    conn.execute("DELETE FROM mediazione_site_checks WHERE registration_number=?", (number,))
                conn.execute(
                    "INSERT INTO mediazione_organismi VALUES (?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(registration_number) DO UPDATE SET name=excluded.name, "
                    "active=excluded.active, website=excluded.website, registry_source=excluded.registry_source, "
                    "registry_checked_at=excluded.registry_checked_at, record_json=excluded.record_json",
                    (number, row["name"], int(bool(row.get("is_active"))), website, source, checked_at,
                     json.dumps(row, ensure_ascii=False)),
                )
            conn.execute("INSERT INTO mediazione_directory_audit VALUES (?, ?, ?, ?, ?)",
                         (uuid4().hex, utc_now(), "registry_import", len(organisms), source))
        return len(organisms)

    def save_check(self, number: str, result: dict) -> None:
        if result.get("registration_number") != number or not result.get("checked_at"):
            raise ValueError("Esito non associato all'organismo.")
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO mediazione_site_checks VALUES (?, ?, ?, ?) "
                "ON CONFLICT(registration_number) DO UPDATE SET checked_at=excluded.checked_at, "
                "status=excluded.status, result_json=excluded.result_json",
                (number, result["checked_at"], result["status"], json.dumps(result, ensure_ascii=False)),
            )
            conn.execute("INSERT INTO mediazione_directory_audit VALUES (?, ?, ?, ?, ?)",
                         (uuid4().hex, utc_now(), "site_check", 1, number))

    def records(self, *, active_only: bool = True) -> list[dict]:
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT o.*, c.result_json FROM mediazione_organismi o "
                "LEFT JOIN mediazione_site_checks c ON c.registration_number=o.registration_number "
                + ("WHERE o.active=1 " if active_only else "") + "ORDER BY o.name"
            ).fetchall()
        return [dict(json.loads(row["record_json"]),
                     registry_checked_at=row["registry_checked_at"],
                     directory_check=json.loads(row["result_json"]) if row["result_json"] else None)
                for row in rows]

    def summary(self) -> dict:
        with self.connection() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM mediazione_organismi").fetchone()["n"]
            active = conn.execute("SELECT COUNT(*) AS n FROM mediazione_organismi WHERE active=1").fetchone()["n"]
            statuses = conn.execute(
                "SELECT c.status, COUNT(*) AS n FROM mediazione_site_checks c JOIN mediazione_organismi o "
                "ON o.registration_number=c.registration_number WHERE o.active=1 GROUP BY c.status"
            ).fetchall()
        counts = {r["status"]: r["n"] for r in statuses}
        return {"source_of_truth": self.source_of_truth, "organisms": total, "active": active,
                "checked": sum(counts.values()), "pending": active - sum(counts.values()), "statuses": counts}

    def save_offices(self, number: str, snapshot: dict) -> None:
        if not snapshot.get("checked_at") or len(snapshot["offices"]) != snapshot["expected_count"]:
            raise ValueError("Inventario sedi incompleto: nessuna sostituzione dei dati verificati.")
        with self.connection() as conn:
            conn.execute(
                "INSERT INTO mediazione_office_snapshots VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(registration_number) DO UPDATE SET checked_at=excluded.checked_at, "
                "source_url=excluded.source_url, expected_count=excluded.expected_count, "
                "pages=excluded.pages, content_sha256=excluded.content_sha256, offices_json=excluded.offices_json",
                (number, snapshot["checked_at"], snapshot["source_url"], snapshot["expected_count"],
                 snapshot["pages"], snapshot["content_sha256"], json.dumps(snapshot["offices"], ensure_ascii=False)),
            )
            conn.execute("INSERT INTO mediazione_directory_audit VALUES (?, ?, ?, ?, ?)",
                         (uuid4().hex, utc_now(), "official_offices_import", len(snapshot["offices"]), snapshot["source_url"]))

    def office_snapshots(self, number: str = "") -> dict[str, dict]:
        with self.connection() as conn:
            rows = conn.execute("SELECT * FROM mediazione_office_snapshots" +
                                (" WHERE registration_number=?" if number else ""),
                                (number,) if number else ()).fetchall()
        return {row["registration_number"]: {
            "offices": json.loads(row["offices_json"]), "checked_at": row["checked_at"],
            "source_url": row["source_url"], "expected_count": row["expected_count"], "pages": row["pages"],
        } for row in rows}
