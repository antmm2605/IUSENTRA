"""Avanzamento persistente per tenant dell'importazione, senza dati dei clienti."""
from __future__ import annotations
import sqlite3
import time
import uuid
from pathlib import Path


class ImportProgress:
    def __init__(self, root, import_id):
        self.path = Path(root) / "import-progress.sqlite"
        self.import_id = import_id
        self.run_id = uuid.uuid4().hex
        self.last_update = 0.0
        self.phase = ""
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (import_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, status TEXT NOT NULL, phase TEXT NOT NULL, done INTEGER NOT NULL, total INTEGER NOT NULL, updated_at REAL NOT NULL)")
            db.execute("UPDATE runs SET status='interrupted' WHERE status='running'")
            db.execute("INSERT OR REPLACE INTO runs VALUES (?, ?, 'running', 'Preparazione', 0, 0, ?)", (import_id, self.run_id, time.time()))

    def update(self, phase, done, total):
        now = time.monotonic()
        if phase == self.phase and now - self.last_update < 1 and done != total:
            return
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE runs SET phase=?, done=?, total=?, updated_at=? WHERE import_id=? AND run_id=?", (phase, done, total, time.time(), self.import_id, self.run_id))
        self.phase, self.last_update = phase, now

    def finish(self, status):
        if status not in {"complete", "partial", "failed"}:
            raise ValueError("Stato non valido")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE runs SET status=?, updated_at=? WHERE import_id=? AND run_id=?", (status, time.time(), self.import_id, self.run_id))


def read_import_progress(root, import_id):
    path = Path(root) / "import-progress.sqlite"
    if not path.is_file():
        return {"status": "idle"}
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("SELECT run_id,status,phase,done,total,updated_at FROM runs WHERE import_id=?", (import_id,)).fetchone()
    if row is None:
        return {"status": "idle"}
    return dict(zip(("runId", "status", "phase", "done", "total", "updatedAt"), row))


class ImportBusy(RuntimeError):
    pass


from contextlib import contextmanager


@contextmanager
def import_lock(path):
    """Lock cross-process nativo SQLite, liberato anche alla morte del worker."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=0)
    try:
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if (getattr(exc, "sqlite_errorcode", 0) & 255) in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                raise ImportBusy("Importazione già in corso") from exc
            raise
        yield
    finally:
        connection.close()
