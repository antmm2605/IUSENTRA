from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.installation_packs import derive_installation_pack_repository_db_path
from pct.postgres_runtime_support import PostgresRepositoryBackend


SCHEMA_INSTALLATION_PACK_SQL = Path(__file__).with_name("sql") / "20260422_installation_pack.sql"
POSTGRES_SCHEMA_INSTALLATION_PACK_SQL = Path(__file__).with_name("sql") / "20260422_installation_pack_postgres.sql"


def _manifest_integrity_ref(payload: dict[str, Any]) -> str:
    return str(payload.get("manifest_hash_sha256") or payload.get("signature") or "")


class InstallationPackRepository:
    def __init__(
        self,
        db_path: str,
        *,
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(postgres_schema_path or POSTGRES_SCHEMA_INSTALLATION_PACK_SQL)
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()

    @classmethod
    def from_registry_path(
        cls,
        registry_path: str,
        *,
        postgres_dsn: str = "",
    ) -> "InstallationPackRepository":
        return cls(
            derive_installation_pack_repository_db_path(registry_path),
            postgres_dsn=postgres_dsn,
        )

    def _connect(self):
        if self._postgres_backend is not None:
            return self._postgres_backend.connection()
        target = Path(self.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _ensure_schema(self) -> None:
        schema = (
            self.postgres_schema_path.read_text(encoding="utf-8")
            if self._postgres_backend is not None
            else SCHEMA_INSTALLATION_PACK_SQL.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def upsert_product_pack(self, payload: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO installation_product_pack_manifest (
                    manifest_id, generated_at, version, installation_id, signature, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(manifest_id) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    version = excluded.version,
                    installation_id = excluded.installation_id,
                    signature = excluded.signature,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    "current",
                    str(payload.get("generated_at") or ""),
                    str(payload.get("version") or ""),
                    str(payload.get("installation_id") or ""),
                    _manifest_integrity_ref(payload),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            conn.commit()

    def upsert_studio_local_pack(self, payload: dict[str, Any]) -> None:
        studio_slug = str(payload.get("studio_slug") or "").strip().lower()
        if not studio_slug:
            return
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO installation_studio_local_pack_manifest (
                    studio_slug, generated_at, installation_id, studio_id, studio_nome,
                    database_backend, signature, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(studio_slug) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    installation_id = excluded.installation_id,
                    studio_id = excluded.studio_id,
                    studio_nome = excluded.studio_nome,
                    database_backend = excluded.database_backend,
                    signature = excluded.signature,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    studio_slug,
                    str(payload.get("generated_at") or ""),
                    str(payload.get("installation_id") or ""),
                    str(payload.get("studio_id") or ""),
                    str(payload.get("studio_nome") or ""),
                    str(payload.get("database_backend") or ""),
                    _manifest_integrity_ref(payload),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            conn.commit()

    def upsert_update_pack(self, payload: dict[str, Any]) -> None:
        to_version = str(payload.get("to_version") or "").strip()
        manifest_id = to_version or "current"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO installation_update_pack_manifest (
                    manifest_id, generated_at, from_version, to_version, installation_id,
                    signature, payload_json, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(manifest_id) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    from_version = excluded.from_version,
                    to_version = excluded.to_version,
                    installation_id = excluded.installation_id,
                    signature = excluded.signature,
                    payload_json = excluded.payload_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    manifest_id,
                    str(payload.get("generated_at") or ""),
                    str(payload.get("from_version") or ""),
                    to_version,
                    str(payload.get("installation_id") or ""),
                    _manifest_integrity_ref(payload),
                    json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
                ),
            )
            conn.commit()

    def load_snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            product_row = conn.execute(
                "SELECT payload_json FROM installation_product_pack_manifest WHERE manifest_id = ?",
                ("current",),
            ).fetchone()
            update_row = conn.execute(
                "SELECT payload_json FROM installation_update_pack_manifest ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
            studio_rows = conn.execute(
                "SELECT payload_json FROM installation_studio_local_pack_manifest ORDER BY studio_slug"
            ).fetchall()
        return {
            "product_pack": json.loads((product_row["payload_json"] if product_row else "{}") or "{}"),
            "update_pack": json.loads((update_row["payload_json"] if update_row else "{}") or "{}"),
            "studio_local_packs": [
                json.loads((row["payload_json"] or "{}"))
                for row in studio_rows or []
            ],
        }

    def storage_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            product_row = conn.execute("SELECT COUNT(*) FROM installation_product_pack_manifest").fetchone()
            studio_row = conn.execute("SELECT COUNT(*) FROM installation_studio_local_pack_manifest").fetchone()
            update_row = conn.execute("SELECT COUNT(*) FROM installation_update_pack_manifest").fetchone()
        return {
            "backend_kind": self.backend_kind,
            "product_packs": int((product_row or [0])[0] or 0),
            "studio_local_packs": int((studio_row or [0])[0] or 0),
            "update_packs": int((update_row or [0])[0] or 0),
            "db_path": self.db_path,
        }
