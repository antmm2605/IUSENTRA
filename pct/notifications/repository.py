"""Repository persistente tenant-aware per notifiche e subscription push."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .models import (
    NotificationPreferences,
    NotificationRecord,
    PushSubscriptionRecord,
    utc_now_iso,
)


SQLITE_SCHEMA_NOTIFICATIONS = Path(__file__).resolve().parents[1] / "sql" / "20260512_notifications.sql"
POSTGRES_SCHEMA_NOTIFICATIONS = Path(__file__).resolve().parents[1] / "sql" / "20260512_notifications_postgres.sql"


def _postgres_backend_type() -> type[Any] | None:
    return PostgresRepositoryBackend if isinstance(PostgresRepositoryBackend, type) else None


class NotificationRepository:
    """Archivio SQL per centro notifiche interno e Web Push."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        postgres_dsn: str = "",
        postgres_schema_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(postgres_schema_path or POSTGRES_SCHEMA_NOTIFICATIONS)
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        backend_cls = _postgres_backend_type()
        if self.postgres_dsn and backend_cls is None:
            raise RuntimeError("Backend PostgreSQL notifiche non disponibile.")
        self._postgres_backend = (
            backend_cls(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn and backend_cls is not None
            else None
        )
        self._ensure_schema()

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        if self._postgres_backend is not None:
            with self._postgres_backend.connection() as conn:
                yield conn
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        schema = (
            self.postgres_schema_path.read_text(encoding="utf-8")
            if self._postgres_backend is not None
            else SQLITE_SCHEMA_NOTIFICATIONS.read_text(encoding="utf-8")
        )
        with self._connect() as conn:
            conn.executescript(schema)

    @staticmethod
    def _dict_row(row: Any) -> dict[str, Any]:
        return dict(row) if row is not None else {}

    def upsert_notification(self, notification: NotificationRecord) -> tuple[NotificationRecord, bool]:
        record = notification.normalized()
        if not record.tenant_id or not record.user_id:
            raise ValueError("tenant_id e user_id sono obbligatori.")
        if not record.dedupe_key:
            record.dedupe_key = f"{record.source_type}:{record.source_id}:{record.type}:{record.id}"[:240]
        payload = record.to_db()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM notifications
                WHERE tenant_id = ? AND user_id = ? AND dedupe_key = ?
                """,
                (record.tenant_id, record.user_id, record.dedupe_key),
            ).fetchone()
            if existing:
                row = self._dict_row(existing)
                record.id = str(row.get("id") or record.id)
                record.created_at = str(row.get("created_at") or record.created_at)
                record.read_at = str(row.get("read_at") or "")
                payload = record.to_db()
                conn.execute(
                    """
                    UPDATE notifications
                    SET type = ?, priority = ?, title = ?, body = ?, href = ?,
                        source_type = ?, source_id = ?, expires_at = ?, payload_json = ?
                    WHERE tenant_id = ? AND user_id = ? AND dedupe_key = ?
                    """,
                    (
                        payload["type"],
                        payload["priority"],
                        payload["title"],
                        payload["body"],
                        payload["href"],
                        payload["source_type"],
                        payload["source_id"],
                        payload["expires_at"],
                        payload["payload_json"],
                        record.tenant_id,
                        record.user_id,
                        record.dedupe_key,
                    ),
                )
                return record, False
            conn.execute(
                """
                INSERT INTO notifications (
                    id, tenant_id, user_id, type, priority, title, body, href,
                    source_type, source_id, dedupe_key, created_at, read_at,
                    expires_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["tenant_id"],
                    payload["user_id"],
                    payload["type"],
                    payload["priority"],
                    payload["title"],
                    payload["body"],
                    payload["href"],
                    payload["source_type"],
                    payload["source_id"],
                    payload["dedupe_key"],
                    payload["created_at"],
                    payload["read_at"],
                    payload["expires_at"],
                    payload["payload_json"],
                ),
            )
            return record, True

    def list_notifications(self, tenant_id: str, user_id: str, *, limit: int = 50) -> list[NotificationRecord]:
        safe_limit = max(1, min(int(limit or 50), 200))
        now = utc_now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM notifications
                WHERE tenant_id = ? AND user_id = ?
                  AND (expires_at = '' OR expires_at IS NULL OR expires_at > ?)
                ORDER BY
                  CASE priority WHEN 'urgent' THEN 0 WHEN 'important' THEN 1 ELSE 2 END,
                  created_at DESC
                LIMIT ?
                """,
                (str(tenant_id or ""), str(user_id or ""), now, safe_limit),
            ).fetchall()
        return [NotificationRecord.from_mapping(self._dict_row(row)) for row in rows]

    def expire_notifications_not_in_dedupe_keys(
        self,
        tenant_id: str,
        user_id: str,
        *,
        active_dedupe_keys: set[str],
        source_types: set[str],
    ) -> int:
        safe_sources = [str(value or "").strip() for value in source_types if str(value or "").strip()]
        if not safe_sources:
            return 0
        active_keys = [str(value or "").strip() for value in active_dedupe_keys if str(value or "").strip()]
        source_placeholders = ",".join("?" for _ in safe_sources)
        key_clause = ""
        params: list[Any] = [
            utc_now_iso(),
            str(tenant_id or ""),
            str(user_id or ""),
            utc_now_iso(),
            *safe_sources,
        ]
        if active_keys:
            key_placeholders = ",".join("?" for _ in active_keys)
            key_clause = f" AND dedupe_key NOT IN ({key_placeholders})"
            params.extend(active_keys)
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                UPDATE notifications
                SET expires_at = ?
                WHERE tenant_id = ? AND user_id = ?
                  AND (expires_at = '' OR expires_at IS NULL OR expires_at > ?)
                  AND source_type IN ({source_placeholders})
                  {key_clause}
                """,
                tuple(params),
            )
            return int(getattr(cur, "rowcount", 0) or 0)

    def mark_read(self, tenant_id: str, user_id: str, notification_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE notifications
                SET read_at = ?
                WHERE tenant_id = ? AND user_id = ? AND id = ?
                """,
                (utc_now_iso(), str(tenant_id or ""), str(user_id or ""), str(notification_id or "")),
            )
            return bool(getattr(cur, "rowcount", 0))

    def mark_all_read(self, tenant_id: str, user_id: str) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE notifications
                SET read_at = ?
                WHERE tenant_id = ? AND user_id = ? AND (read_at = '' OR read_at IS NULL)
                """,
                (utc_now_iso(), str(tenant_id or ""), str(user_id or "")),
            )
            return int(getattr(cur, "rowcount", 0) or 0)

    def upsert_subscription(self, subscription: PushSubscriptionRecord) -> tuple[PushSubscriptionRecord, bool]:
        record = subscription.normalized()
        if not record.tenant_id or not record.user_id or not record.endpoint:
            raise ValueError("tenant_id, user_id ed endpoint sono obbligatori.")
        now = utc_now_iso()
        record.last_seen_at = now
        payload = record.to_db()
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM push_subscriptions
                WHERE tenant_id = ? AND user_id = ? AND endpoint = ?
                """,
                (record.tenant_id, record.user_id, record.endpoint),
            ).fetchone()
            if existing:
                row = self._dict_row(existing)
                record.id = str(row.get("id") or record.id)
                record.created_at = str(row.get("created_at") or record.created_at)
                payload = record.to_db()
                conn.execute(
                    """
                    UPDATE push_subscriptions
                    SET p256dh = ?, auth = ?, user_agent = ?, device_label = ?,
                        enabled = 1, last_seen_at = ?, revoked_at = ''
                    WHERE tenant_id = ? AND user_id = ? AND endpoint = ?
                    """,
                    (
                        payload["p256dh"],
                        payload["auth"],
                        payload["user_agent"],
                        payload["device_label"],
                        payload["last_seen_at"],
                        record.tenant_id,
                        record.user_id,
                        record.endpoint,
                    ),
                )
                return record, False
            conn.execute(
                """
                INSERT INTO push_subscriptions (
                    id, tenant_id, user_id, endpoint, p256dh, auth, user_agent,
                    device_label, enabled, created_at, last_seen_at, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["id"],
                    payload["tenant_id"],
                    payload["user_id"],
                    payload["endpoint"],
                    payload["p256dh"],
                    payload["auth"],
                    payload["user_agent"],
                    payload["device_label"],
                    payload["enabled"],
                    payload["created_at"],
                    payload["last_seen_at"],
                    payload["revoked_at"],
                ),
            )
            return record, True

    def list_active_subscriptions(self, tenant_id: str, user_id: str) -> list[PushSubscriptionRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM push_subscriptions
                WHERE tenant_id = ? AND user_id = ? AND enabled = 1
                  AND (revoked_at = '' OR revoked_at IS NULL)
                ORDER BY last_seen_at DESC
                """,
                (str(tenant_id or ""), str(user_id or "")),
            ).fetchall()
        return [PushSubscriptionRecord.from_mapping(self._dict_row(row)) for row in rows]

    def revoke_subscription(
        self,
        tenant_id: str,
        user_id: str,
        *,
        endpoint: str = "",
        subscription_id: str = "",
    ) -> int:
        endpoint = str(endpoint or "").strip()
        subscription_id = str(subscription_id or "").strip()
        if not endpoint and not subscription_id:
            return 0
        clauses = ["tenant_id = ?", "user_id = ?"]
        params: list[Any] = [str(tenant_id or ""), str(user_id or "")]
        if endpoint:
            clauses.append("endpoint = ?")
            params.append(endpoint)
        if subscription_id:
            clauses.append("id = ?")
            params.append(subscription_id)
        params = [utc_now_iso(), *params]
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                UPDATE push_subscriptions
                SET enabled = 0, revoked_at = ?
                WHERE {' AND '.join(clauses)}
                """,
                tuple(params),
            )
            return int(getattr(cur, "rowcount", 0) or 0)

    def disable_subscription_by_id(self, subscription_id: str, *, tenant_id: str = "", user_id: str = "") -> int:
        clauses = ["id = ?"]
        params: list[Any] = [str(subscription_id or "")]
        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)
        if user_id:
            clauses.append("user_id = ?")
            params.append(user_id)
        params = [utc_now_iso(), *params]
        with self._connect() as conn:
            cur = conn.execute(
                f"""
                UPDATE push_subscriptions
                SET enabled = 0, revoked_at = ?
                WHERE {' AND '.join(clauses)}
                """,
                tuple(params),
            )
            return int(getattr(cur, "rowcount", 0) or 0)

    def get_preferences(self, tenant_id: str, user_id: str) -> NotificationPreferences:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM notification_preferences
                WHERE tenant_id = ? AND user_id = ?
                """,
                (str(tenant_id or ""), str(user_id or "")),
            ).fetchone()
        if not row:
            return NotificationPreferences.defaults(tenant_id, user_id)
        return NotificationPreferences.from_mapping(self._dict_row(row), tenant_id, user_id)

    def save_preferences(self, preferences: NotificationPreferences) -> NotificationPreferences:
        prefs = preferences
        prefs.updated_at = utc_now_iso()
        payload = prefs.to_db()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notification_preferences (
                    tenant_id, user_id, push_enabled, notify_urgent,
                    notify_important, notify_normal, quiet_hours_enabled,
                    quiet_hours_start, quiet_hours_end, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id) DO UPDATE SET
                    push_enabled = excluded.push_enabled,
                    notify_urgent = excluded.notify_urgent,
                    notify_important = excluded.notify_important,
                    notify_normal = excluded.notify_normal,
                    quiet_hours_enabled = excluded.quiet_hours_enabled,
                    quiet_hours_start = excluded.quiet_hours_start,
                    quiet_hours_end = excluded.quiet_hours_end,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["tenant_id"],
                    payload["user_id"],
                    payload["push_enabled"],
                    payload["notify_urgent"],
                    payload["notify_important"],
                    payload["notify_normal"],
                    payload["quiet_hours_enabled"],
                    payload["quiet_hours_start"],
                    payload["quiet_hours_end"],
                    payload["updated_at"],
                ),
            )
        return prefs

    def record_delivery(
        self,
        *,
        tenant_id: str,
        user_id: str,
        notification_id: str,
        channel: str,
        status: str,
        detail: str = "",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO notification_deliveries (
                    tenant_id, user_id, notification_id, channel, status, detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(tenant_id or ""),
                    str(user_id or ""),
                    str(notification_id or ""),
                    str(channel or "internal")[:40],
                    str(status or "")[:80],
                    str(detail or "")[:500],
                    utc_now_iso(),
                ),
            )
