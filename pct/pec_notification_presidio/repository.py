from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .models import required_text
from .repository_audit import NotificationPresidioAuditMixin
from .repository_mutations import NotificationPresidioMutationMixin
from .repository_queries import NotificationPresidioQueryMixin
from .repository_receipts import NotificationPresidioReceiptMixin
from .repository_transition_chain import NotificationPresidioTransitionChainMixin
from .repository_transitions import NotificationPresidioTransitionMixin


SQLITE_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1] / "sql" / "20260719_pec_legal_notification_presidio.sql"
)
POSTGRES_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "sql"
    / "20260719_pec_legal_notification_presidio_postgres.sql"
)

class NotificationPresidioRepository(
    NotificationPresidioTransitionChainMixin,
    NotificationPresidioMutationMixin,
    NotificationPresidioTransitionMixin,
    NotificationPresidioReceiptMixin,
    NotificationPresidioQueryMixin,
    NotificationPresidioAuditMixin,
):
    """Repository tenant-bound; il tenant non è mai accettato dai payload pubblici."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        tenant_id: str,
        postgres_dsn: str = "",
        sqlite_schema_path: str | Path = SQLITE_SCHEMA_PATH,
        postgres_schema_path: str | Path = POSTGRES_SCHEMA_PATH,
    ) -> None:
        self.tenant_id = required_text(tenant_id, "tenant_id")
        self.db_path = Path(db_path)
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self.sqlite_schema_path = Path(sqlite_schema_path)
        self.postgres_schema_path = Path(postgres_schema_path)
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        if self._postgres_backend is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_sqlite_schema()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        if self._postgres_backend is not None:
            with self._postgres_backend.connection() as conn:
                yield conn
            return
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def close(self) -> None:
        if self._postgres_backend is not None:
            self._postgres_backend.close()

    def _ensure_sqlite_schema(self) -> None:
        schema = self.sqlite_schema_path.read_text(encoding="utf-8")
        with self.connection() as conn:
            conn.executescript(schema)

    @staticmethod
    def _row(row: Any) -> dict[str, Any]:
        return dict(row) if row is not None else {}

    @staticmethod
    def _uuid() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _insert_sql(table: str, columns: Sequence[str]) -> str:
        placeholders = ",".join("?" for _ in columns)
        return f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})"

    def _presidio_row(self, conn: Any, presidio_id: str, *, lock: bool = False) -> dict[str, Any]:
        sql = "SELECT * FROM pec_legal_notification_presidia WHERE tenant_id=? AND id=?"
        if lock and self.backend_kind == "postgresql":
            sql += " FOR UPDATE"
        row = conn.execute(sql, (self.tenant_id, required_text(presidio_id, "presidio_id"))).fetchone()
        if row is None:
            raise KeyError("Presidio non trovato per il tenant corrente")
        return self._row(row)

    def get_presidio(self, presidio_id: str) -> dict[str, Any]:
        with self.connection() as conn:
            return self._presidio_row(conn, presidio_id)
