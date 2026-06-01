from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend
from pct.support_remote import (
    derive_support_repository_db_path,
    generate_support_client_token,
    generate_support_public_id,
    parse_json_payload,
    safe_json_payload,
)


SCHEMA_SUPPORT_REMOTE_SQL = Path(__file__).with_name("sql") / "20260422_support_remote.sql"
POSTGRES_SCHEMA_SUPPORT_REMOTE_SQL = Path(__file__).with_name("sql") / "20260422_support_remote_postgres.sql"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_utc_timestamp(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()
    text = str(value or "").strip()
    if not text:
        return ""
    normalized = text.replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return text
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


class SupportRemoteRepository:
    def __init__(
        self,
        db_path: str,
        *,
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(postgres_schema_path or POSTGRES_SCHEMA_SUPPORT_REMOTE_SQL)
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self._ensure_schema()

    @classmethod
    def from_anchor_path(
        cls,
        anchor_path: str,
        *,
        postgres_dsn: str = "",
    ) -> "SupportRemoteRepository":
        return cls(
            derive_support_repository_db_path(anchor_path),
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
            else SCHEMA_SUPPORT_REMOTE_SQL.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)
            conn.commit()

    def _row_to_dict(self, row: Any) -> dict[str, Any] | None:
        if row is None:
            return None
        if isinstance(row, dict):
            payload = dict(row)
        elif hasattr(row, "keys"):
            payload = {key: row[key] for key in row.keys()}
        else:
            return None
        for key in (
            "consent_screen",
            "consent_audio",
            "consent_chat",
            "consent_advanced_control",
            "advanced_control_requested",
            "advanced_control_approved",
        ):
            if key in payload:
                payload[key] = bool(payload[key])
        if "payload_json" in payload:
            payload["payload"] = parse_json_payload(payload.get("payload_json"))
        for key in ("created_at", "updated_at", "started_at", "ended_at"):
            if key in payload:
                payload[key] = _normalize_utc_timestamp(payload.get(key))
        return payload

    def _sanitize_session(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            "id": int(row.get("id") or 0),
            "public_id": str(row.get("public_id") or ""),
            "client_token": str(row.get("client_token") or ""),
            "studio_slug": str(row.get("studio_slug") or ""),
            "studio_nome": str(row.get("studio_nome") or ""),
            "practice_id": str(row.get("practice_id") or ""),
            "practice_label": str(row.get("practice_label") or ""),
            "client_id": str(row.get("client_id") or ""),
            "customer_name": str(row.get("customer_name") or ""),
            "customer_email": str(row.get("customer_email") or ""),
            "created_by": str(row.get("created_by") or ""),
            "assigned_to": str(row.get("assigned_to") or ""),
            "status": str(row.get("status") or "created"),
            "consent_screen": bool(row.get("consent_screen")),
            "consent_audio": bool(row.get("consent_audio")),
            "consent_chat": bool(row.get("consent_chat", True)),
            "consent_advanced_control": bool(row.get("consent_advanced_control")),
            "advanced_control_requested": bool(row.get("advanced_control_requested")),
            "advanced_control_approved": bool(row.get("advanced_control_approved")),
            "started_at": str(row.get("started_at") or ""),
            "ended_at": str(row.get("ended_at") or ""),
            "notes": str(row.get("notes") or ""),
            "created_at": _normalize_utc_timestamp(row.get("created_at")),
            "updated_at": _normalize_utc_timestamp(row.get("updated_at")),
        }

    def create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        public_id = str(payload.get("public_id") or generate_support_public_id())
        client_token = str(payload.get("client_token") or generate_support_client_token())
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO support_session (
                    public_id, client_token, studio_slug, studio_nome, practice_id, practice_label,
                    client_id, customer_name, customer_email, created_by, assigned_to, status,
                    consent_screen, consent_audio, consent_chat, consent_advanced_control,
                    advanced_control_requested, advanced_control_approved, started_at, ended_at, notes,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    public_id,
                    client_token,
                    str(payload.get("studio_slug") or "").strip().lower(),
                    str(payload.get("studio_nome") or "").strip(),
                    str(payload.get("practice_id") or "").strip(),
                    str(payload.get("practice_label") or "").strip(),
                    str(payload.get("client_id") or "").strip(),
                    str(payload.get("customer_name") or "").strip(),
                    str(payload.get("customer_email") or "").strip(),
                    str(payload.get("created_by") or "").strip(),
                    str(payload.get("assigned_to") or "").strip(),
                    str(payload.get("status") or "created").strip() or "created",
                    1 if payload.get("consent_screen") else 0,
                    1 if payload.get("consent_audio") else 0,
                    0 if payload.get("consent_chat") is False else 1,
                    1 if payload.get("consent_advanced_control") else 0,
                    1 if payload.get("advanced_control_requested") else 0,
                    1 if payload.get("advanced_control_approved") else 0,
                    str(payload.get("started_at") or "").strip(),
                    str(payload.get("ended_at") or "").strip(),
                    str(payload.get("notes") or "").strip(),
                    _normalize_utc_timestamp(payload.get("created_at")) or now,
                    _normalize_utc_timestamp(payload.get("updated_at")) or now,
                ),
            )
            conn.commit()
        return self.get_session_by_public_id(public_id) or {}

    def get_session_by_public_id(self, public_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM support_session WHERE public_id = ? LIMIT 1",
                (str(public_id or "").strip(),),
            ).fetchone()
        return self._sanitize_session(self._row_to_dict(row))

    def get_session_by_client_token(self, client_token: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM support_session WHERE client_token = ? LIMIT 1",
                (str(client_token or "").strip(),),
            ).fetchone()
        return self._sanitize_session(self._row_to_dict(row))

    def update_session(self, public_id: str, **updates: Any) -> dict[str, Any] | None:
        allowed = {
            "studio_slug",
            "studio_nome",
            "practice_id",
            "practice_label",
            "client_id",
            "customer_name",
            "customer_email",
            "assigned_to",
            "status",
            "consent_screen",
            "consent_audio",
            "consent_chat",
            "consent_advanced_control",
            "advanced_control_requested",
            "advanced_control_approved",
            "started_at",
            "ended_at",
            "notes",
        }
        fields: list[str] = []
        params: list[Any] = []
        for key, value in updates.items():
            if key not in allowed:
                continue
            fields.append(f"{key} = ?")
            if key.startswith("consent_") or key.startswith("advanced_control_"):
                params.append(1 if value else 0)
            else:
                params.append(str(value).strip() if value is not None and not isinstance(value, bool) else value)
        if not fields:
            return self.get_session_by_public_id(public_id)
        fields.append("updated_at = ?")
        params.append(_utc_now_iso())
        params.append(str(public_id or "").strip())
        with self._connect() as conn:
            conn.execute(
                f"UPDATE support_session SET {', '.join(fields)} WHERE public_id = ?",
                tuple(params),
            )
            conn.commit()
        return self.get_session_by_public_id(public_id)

    def append_event(
        self,
        public_id: str,
        *,
        event_type: str,
        actor_role: str = "",
        actor_name: str = "",
        story_line: str = "",
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        session_row = self.get_session_by_public_id(public_id)
        if session_row is None:
            return None
        now = _utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO support_event (
                    session_id, public_id, event_type, actor_role, actor_name, story_line, payload_json,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(session_row["id"]),
                    session_row["public_id"],
                    str(event_type or "").strip(),
                    str(actor_role or "").strip(),
                    str(actor_name or "").strip(),
                    str(story_line or "").strip(),
                    safe_json_payload(payload),
                    now,
                ),
            )
            conn.execute(
                "UPDATE support_session SET updated_at = ? WHERE public_id = ?",
                (now, session_row["public_id"]),
            )
            conn.commit()
        return self.get_session_by_public_id(public_id)

    def list_events(self, public_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM support_event
                WHERE public_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (str(public_id or "").strip(), int(limit or 200)),
            ).fetchall()
        events = [self._row_to_dict(row) or {} for row in rows or []]
        return list(reversed(events))

    def list_sessions(
        self,
        *,
        limit: int = 50,
        status: str = "",
        search: str = "",
        studio_slug: str = "",
    ) -> list[dict[str, Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(str(status).strip())
        if studio_slug:
            clauses.append("studio_slug = ?")
            params.append(str(studio_slug).strip().lower())
        if search:
            token = f"%{str(search).strip().lower()}%"
            clauses.append(
                """
                (
                    LOWER(public_id) LIKE ?
                    OR LOWER(customer_name) LIKE ?
                    OR LOWER(customer_email) LIKE ?
                    OR LOWER(practice_label) LIKE ?
                    OR LOWER(studio_nome) LIKE ?
                )
                """
            )
            params.extend([token, token, token, token, token])
        params.append(int(limit or 50))
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM support_session
                WHERE {' AND '.join(clauses)}
                ORDER BY
                    CASE status
                        WHEN 'waiting_operator' THEN 0
                        WHEN 'created' THEN 1
                        WHEN 'waiting_client' THEN 2
                        WHEN 'waiting_peer' THEN 3
                        WHEN 'active' THEN 4
                        ELSE 5
                    END,
                    updated_at DESC,
                    id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [self._sanitize_session(self._row_to_dict(row)) or {} for row in rows or []]

    def delete_session(self, public_id: str) -> bool:
        session_row = self.get_session_by_public_id(public_id)
        if session_row is None:
            return False
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM support_session WHERE public_id = ?",
                (str(public_id or "").strip(),),
            )
            conn.commit()
        return self.get_session_by_public_id(public_id) is None

    @staticmethod
    def _looks_like_test_session(row: dict[str, Any]) -> bool:
        haystack = " ".join(
            str(row.get(key) or "")
            for key in (
                "customer_name",
                "customer_email",
                "practice_label",
                "studio_nome",
                "notes",
                "created_by",
            )
        ).lower()
        markers = (
            "test",
            "prova",
            "smoke",
            "e2e",
            "locale 8080",
            "reale 8080",
            "test reale",
            "controllo pc reale",
        )
        return any(marker in haystack for marker in markers)

    def delete_test_sessions(self, *, limit: int = 500) -> int:
        deleted = 0
        for row in self.list_sessions(limit=limit):
            if not self._looks_like_test_session(row):
                continue
            if self.delete_session(str(row.get("public_id") or "")):
                deleted += 1
        return deleted

    def stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            total_row = conn.execute("SELECT COUNT(*) FROM support_session").fetchone()
            open_row = conn.execute(
                "SELECT COUNT(*) FROM support_session WHERE status IN ('created', 'waiting_operator', 'waiting_client', 'waiting_peer', 'active')"
            ).fetchone()
            active_row = conn.execute(
                "SELECT COUNT(*) FROM support_session WHERE status = 'active'"
            ).fetchone()
            closed_row = conn.execute(
                "SELECT COUNT(*) FROM support_session WHERE status = 'closed'"
            ).fetchone()
        return {
            "backend_kind": self.backend_kind,
            "db_path": self.db_path,
            "totale_sessioni": int((total_row or [0])[0] or 0),
            "aperte": int((open_row or [0])[0] or 0),
            "attive": int((active_row or [0])[0] or 0),
            "chiuse": int((closed_row or [0])[0] or 0),
        }
