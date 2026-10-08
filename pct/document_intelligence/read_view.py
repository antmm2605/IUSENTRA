"""Sola consultazione SQL mediante i getter nativi, senza migrazioni o JSON."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from .repository import DocumentAIRepository


class SQLDocumentAIReader:
    def __init__(self, structured_db):
        reader = DocumentAIRepository.__new__(DocumentAIRepository)
        reader.structured_db = structured_db
        reader._backend = reader._detect_backend(structured_db)
        if reader._backend not in {"sqlite", "postgresql"}:
            raise ValueError("Repository SQL documentale non disponibile")
        self._reader = reader
        self.backend_kind = reader.backend_kind

    def get_document(self, tenant, fascicolo, document):
        return self._reader.get_document(tenant, fascicolo, document)

    def list_documents(self, tenant, fascicolo):
        return self._reader.list_documents(tenant, fascicolo)

    def get_extracted_text(self, tenant, fascicolo, document, version):
        return self._reader.get_extracted_text(tenant, fascicolo, document, version)


@contextmanager
def source_snapshot(core):
    """Inventario e testo nella stessa fotografia SQL, senza DDL o immutable.

    Connessione dedicata: non commette né altera transazioni del chiamante.
    PostgreSQL usa REPEATABLE READ; SQLite conserva il WAL corrente.
    """
    if getattr(core, "backend_kind", "") == "postgresql":
        import psycopg2
        from pct.storage_postgres import PostgresCompatConnection

        raw = psycopg2.connect(core.dsn, connect_timeout=5)
        raw.set_session(isolation_level="REPEATABLE READ", readonly=True)
        view = SimpleNamespace(backend_kind="postgresql", raw_conn=raw)
        view.conn = PostgresCompatConnection(view)
    else:
        path = Path(core.db_path).resolve(strict=True)
        raw = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA query_only=ON")
        raw.execute("BEGIN")
        view = SimpleNamespace(backend_kind="sqlite", conn=raw)
    try:
        yield view
    finally:
        raw.rollback()
        raw.close()
