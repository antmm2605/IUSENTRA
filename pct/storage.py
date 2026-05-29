"""
pct/storage.py — Backend SQLite per-tenant (studio.db).

Ogni tenant ha un singolo database SQLite in:
    {data_root}/studio.db

Attivazione (due modalità):
    1. Variabile d'ambiente: PCT_SQLITE_MODE=1
    2. Passare studio_db=StudioDB(...) direttamente al costruttore del modulo

Lo schema completo (15 tabelle) è definito in pct.database.SCHEMA_SQL e include:
    clienti, fascicoli, appuntamenti, scadenze, messaggi, utenti, audit_log,
    privacy_trattamenti, notifiche_log, backup_records, backup_config,
    search_documenti (FTS5), search_meta_indice, search_ocr_cache, _meta,
    moduli_dati, moduli_json_records

Pattern di accesso nei moduli:
    - _carica_sqlite() → SELECT dati_json FROM table → deserializza
    - _salva_sqlite()  → BEGIN / DELETE / INSERT batch / COMMIT

Thread-safety:
    - Un'istanza StudioDB per percorso per worker Gunicorn
    - Connessioni per-thread via threading.local
    - FK disabilitate durante i _salva_* (full-reload pattern) per evitare
      CASCADE indesiderati; la consistenza FK è garantita dalla logica Python
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict

from pct.path_security import resolve_sqlite_path

# ------------------------------------------------------------------ importazione lazy schema
# Evita importazione circolare se pct.database importasse pct.storage.
def _schema_sql() -> str:
    from pct.database import SCHEMA_SQL
    return SCHEMA_SQL


# ------------------------------------------------------------------ singleton per-processo

_instances: Dict[str, "StudioDB"] = {}
_instances_lock = threading.Lock()
logger = logging.getLogger(__name__)


def _is_locked_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


# ------------------------------------------------------------------ helpers I/O

def _j(value: Any) -> str:
    """Serializza in JSON compatto."""
    return json.dumps(value, ensure_ascii=False)


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Converte sqlite3.Row in dict."""
    return dict(zip(row.keys(), tuple(row)))


# ================================================================== StudioDB

class StudioDB:
    """
    Gestisce il database SQLite per-tenant.

    Una sola istanza per percorso per worker Gunicorn (singleton via .get()).
    Ogni thread/greenlet ha la propria connessione (threading.local).

    Esempio::

        db = StudioDB.get("/data/tenants/mio_studio/studio.db")
        clienti = db.conn.execute("SELECT dati_json FROM clienti").fetchall()
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = resolve_sqlite_path(db_path)
        self._local = threading.local()
        self._ensure_schema()

    @classmethod
    def get(cls, db_path: str) -> "StudioDB":
        """
        Restituisce l'istanza singleton per questo percorso.
        Thread-safe: la creazione è protetta da lock.
        """
        key = str(resolve_sqlite_path(db_path))
        if key not in _instances:
            with _instances_lock:
                if key not in _instances:
                    _instances[key] = cls(key)
        return _instances[key]

    @classmethod
    def invalidate(cls, db_path: str) -> None:
        """Chiude e rimuove l'istanza cache per un database appena sostituito."""
        key = str(resolve_sqlite_path(db_path))
        with _instances_lock:
            instance = _instances.pop(key, None)
        if instance is not None:
            instance.chiudi()

    @classmethod
    def from_data_path(cls, any_data_file: str) -> "StudioDB":
        """
        Deriva il percorso studio.db dalla posizione di un qualunque file dati.

        Logica: sale di due livelli (es. clienti/anagrafica.json → root)
        e costruisce {root}/studio.db.

        Esempio::
            StudioDB.from_data_path("/data/clienti/anagrafica.json")
            → StudioDB.get("/data/studio.db")
        """
        p = Path(any_data_file)
        root = p.parent.parent if p.suffix == ".json" else p.parent
        return cls.get(str(root / "studio.db"))

    # ---------------------------------------------------------------- connessione

    @property
    def conn(self) -> sqlite3.Connection:
        """Connessione per-thread. Apre e configura al primo accesso."""
        if not hasattr(self._local, "_conn") or self._local._conn is None:
            self._local._conn = self._connect()
        return self._local._conn

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            check_same_thread=False,
        )
        c.row_factory = sqlite3.Row
        try:
            c.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as exc:
            logger.warning(
                "SQLite tenant %s: WAL non disponibile, fallback a modalita' DELETE (%s)",
                self.db_path,
                exc,
            )
            c.execute("PRAGMA journal_mode=DELETE")
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=15000")
        c.execute("PRAGMA cache_size=-16000")   # 16 MB page cache
        c.execute("PRAGMA temp_store=MEMORY")
        return c

    # Tabelle che non hanno ancora dati_json nello schema originale.
    # ALTER TABLE ... ADD COLUMN è idempotente (fallisce silenziosamente se già esiste).
    _UPGRADE_ADD_DATI_JSON: tuple = (
        "fascicoli",
        "appuntamenti",
        "scadenze",
        "messaggi",
        "utenti",
    )

    def _ensure_schema(self) -> None:
        """
        Crea il file DB, applica lo schema base e aggiunge le colonne
        dati_json alle tabelle che ne erano prive (upgrade schema idempotente).
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.executescript(_schema_sql())
        # Upgrade: aggiungi dati_json dove mancante
        for table in self._UPGRADE_ADD_DATI_JSON:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN dati_json TEXT DEFAULT '{{}}'"
                )
            except Exception:
                pass  # colonna già presente — ok
        # Registra data creazione
        conn.execute(
            "INSERT OR IGNORE INTO _meta VALUES (?,?)",
            ("creato_il", __import__("datetime").datetime.now().isoformat()),
        )
        conn.commit()
        self._local._conn = conn

    def ensure_schema(self) -> None:
        """Riallinea lo schema SQLite corrente ai requisiti runtime."""
        self._ensure_schema()

    # ---------------------------------------------------------------- utilità transazione

    def salva_tabella(
        self,
        table: str,
        rows: list,
        inserter,
        delete_all: bool = True,
    ) -> None:
        """
        Sostituisce atomicamente tutti i record di una tabella.

        1. Disabilita FK (evita CASCADE durante DELETE)
        2. BEGIN
        3. DELETE FROM table (se delete_all=True)
        4. Per ogni elemento di rows chiama inserter(conn, elemento)
        5. COMMIT
        6. Riabilita FK

        Parameters
        ----------
        table:
            Nome tabella SQLite.
        rows:
            Iterable di oggetti da inserire.
        inserter:
            Callable(conn, obj) che esegue la INSERT per un singolo record.
        delete_all:
            Se True (default) cancella tutto e reinserisce (full-replace).
        """
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(5):
            conn = self.conn
            began = False
            try:
                conn.execute("PRAGMA foreign_keys=OFF")
                conn.execute("BEGIN IMMEDIATE")
                began = True
                if delete_all:
                    conn.execute(f"DELETE FROM {table}")
                for row in rows:
                    inserter(conn, row)
                conn.execute("COMMIT")
                return
            except sqlite3.OperationalError as exc:
                last_error = exc
                if began:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                if not _is_locked_error(exc) or attempt == 4:
                    raise
                time.sleep(0.2 * (attempt + 1))
            except Exception:
                if began:
                    try:
                        conn.execute("ROLLBACK")
                    except sqlite3.Error:
                        pass
                raise
            finally:
                try:
                    conn.execute("PRAGMA foreign_keys=ON")
                except sqlite3.Error:
                    pass
        if last_error is not None:
            raise last_error

    def carica_tabella(self, table: str) -> list:
        """
        Legge tutti i record di una tabella come lista di dict.
        Utilizza la colonna dati_json se disponibile (full-object storage).
        """
        try:
            rows = self.conn.execute(
                f"SELECT dati_json FROM {table}"
            ).fetchall()
            result = []
            for row in rows:
                try:
                    result.append(json.loads(row["dati_json"]))
                except (json.JSONDecodeError, KeyError, TypeError):
                    result.append(_row_to_dict(row))
            return result
        except sqlite3.OperationalError:
            return []

    def ha_dati(self, table: str) -> bool:
        """Restituisce True se la tabella ha almeno un record."""
        try:
            row = self.conn.execute(
                f"SELECT COUNT(*) AS n FROM {table}"
            ).fetchone()
            return bool(row and row["n"] > 0)
        except sqlite3.OperationalError:
            return False

    def chiudi(self) -> None:
        """Chiude la connessione del thread corrente."""
        if hasattr(self._local, "_conn") and self._local._conn:
            self._local._conn.close()
            self._local._conn = None
