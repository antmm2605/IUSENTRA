from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend


SCHEMA_WORKSPACE_INTELLIGENCE_REPOSITORY = Path(__file__).with_name("sql") / "20260418_workspace_intelligence_repository.sql"
POSTGRES_SCHEMA_WORKSPACE_INTELLIGENCE_REPOSITORY = Path(__file__).with_name("sql") / "20260418_workspace_intelligence_repository_postgres.sql"


def derive_workspace_intelligence_repository_db_path(snapshot_path: str) -> str:
    target = Path(snapshot_path).resolve()
    return str(target.with_name("workspace_intelligence_repository.db"))


class WorkspaceIntelligenceRepository:
    def __init__(
        self,
        db_path: str,
        *,
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(
            postgres_schema_path or POSTGRES_SCHEMA_WORKSPACE_INTELLIGENCE_REPOSITORY
        )
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()

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
            else SCHEMA_WORKSPACE_INTELLIGENCE_REPOSITORY.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def save_snapshot(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = json.dumps(dict(payload or {}), ensure_ascii=False, default=str)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workspace_intelligence_snapshot (
                    snapshot_id, generated_at, summary_json, actions_json, overview_json, search_text, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    summary_json = excluded.summary_json,
                    actions_json = excluded.actions_json,
                    overview_json = excluded.overview_json,
                    search_text = excluded.search_text,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    "latest",
                    str(payload.get("generated_at") or ""),
                    json.dumps(((payload.get("overview") or {}).get("summary") or {}), ensure_ascii=False),
                    json.dumps(((payload.get("overview") or {}).get("actions") or []), ensure_ascii=False),
                    encoded,
                    "",
                ),
            )
            conn.commit()
        return payload

    def load_snapshot(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT overview_json FROM workspace_intelligence_snapshot WHERE snapshot_id = ?",
                ("latest",),
            ).fetchone()
        if not row:
            return {"generated_at": "", "overview": {}}
        try:
            return dict(json.loads(row["overview_json"] or "{}"))
        except Exception:
            return {"generated_at": "", "overview": {}}

    def storage_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) FROM workspace_intelligence_snapshot").fetchone()
        return {
            "backend_kind": self.backend_kind,
            "workspace_intelligence_snapshots": int((row or [0])[0] or 0),
        }
