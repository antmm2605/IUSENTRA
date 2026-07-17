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
import sys
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
_SQLITE_BUSY_TIMEOUT_MS = 30000
_SQLITE_WRITE_ATTEMPTS = 8


def _is_locked_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message


def _is_readonly_write_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "readonly" in message or "attempt to write" in message


def _requires_delete_journal_for_mount(db_path: Path) -> bool:
    """Evita WAL sui bind mount Windows/9p dove i lock SQLite sono instabili."""
    # Lo stesso studio.db viene aperto sia da Python nativo Windows sia dal
    # container Docker tramite bind mount 9p. Se Windows lo lascia in WAL, il
    # container non riesce piu' ad aprirlo in scrittura. DELETE e' quindi il
    # formato condiviso governato per entrambi i lati del mount.
    if sys.platform == "win32":
        return True
    mounts = Path("/proc/mounts")
    if not mounts.exists():
        return False
    try:
        target = str(db_path.resolve())
        best_mount = ""
        best_type = ""
        for raw_line in mounts.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = raw_line.split()
            if len(parts) < 3:
                continue
            mount_point = parts[1].replace("\\040", " ")
            if target == mount_point or target.startswith(mount_point.rstrip("/") + "/"):
                if len(mount_point) > len(best_mount):
                    best_mount = mount_point
                    best_type = parts[2].casefold()
        return best_type in {"9p", "drvfs", "vboxsf", "fuse.osxfs"}
    except Exception:
        return False


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

    def _conn_query_only(self, conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute("PRAGMA query_only").fetchone()
            return bool(row and int(row[0]) == 1)
        except Exception:
            return False

    def _close_thread_connection(self) -> None:
        conn = getattr(self._local, "_conn", None)
        if conn is not None:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._local._conn = None

    def _conn_per_scrittura(self) -> sqlite3.Connection:
        conn = getattr(self._local, "_conn", None)
        if conn is not None and not self._conn_query_only(conn):
            return conn
        if conn is not None:
            self._close_thread_connection()
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(8):
            try:
                conn = self._connect_writable()
                self._local._conn = conn
                return conn
            except sqlite3.OperationalError as exc:
                last_error = exc
                message = str(exc).lower()
                retryable = _is_locked_error(exc) or "unable to open database file" in message
                if not retryable or attempt == 7:
                    raise
                logger.warning(
                    "SQLite tenant %s: connessione scrivibile occupata, ritento (%s/8): %s",
                    self.db_path,
                    attempt + 2,
                    exc,
                )
                time.sleep(0.25 * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise sqlite3.OperationalError("connessione scrivibile non disponibile")

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
        try:
            return self._connect_writable()
        except sqlite3.OperationalError as exc:
            if not _requires_delete_journal_for_mount(self.db_path):
                raise
            message = str(exc).lower()
            if "unable to open database file" not in message and "database is locked" not in message:
                raise
            logger.warning(
                "SQLite tenant %s: mount locale non compatibile con lock scrivibili, "
                "fallback SQL in sola lettura per le viste React (%s)",
                self.db_path,
                exc,
            )
            return self._connect_readonly_immutable()

    def _connect_writable(self) -> sqlite3.Connection:
        c = sqlite3.connect(
            str(self.db_path),
            timeout=30,
            check_same_thread=False,
        )
        try:
            c.row_factory = sqlite3.Row
            c.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
            self._configure_journal_mode(c)
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA cache_size=-16000")   # 16 MB page cache
            c.execute("PRAGMA temp_store=MEMORY")
            return c
        except Exception:
            c.close()
            raise

    def _configure_journal_mode(self, conn: sqlite3.Connection) -> None:
        """Configura il journal senza trasformare un lock temporaneo in 500."""

        if _requires_delete_journal_for_mount(self.db_path):
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.OperationalError as exc:
                if not (_is_locked_error(exc) or "unable to open database file" in str(exc).lower()):
                    raise
                logger.warning(
                    "SQLite tenant %s: journal DELETE temporaneamente occupato, "
                    "proseguo con la modalita' gia' attiva (%s)",
                    self.db_path,
                    exc,
                )
            return
        try:
            conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError as exc:
            logger.warning(
                "SQLite tenant %s: WAL non disponibile, fallback a modalita' DELETE (%s)",
                self.db_path,
                exc,
            )
            try:
                conn.execute("PRAGMA journal_mode=DELETE")
            except sqlite3.OperationalError as delete_exc:
                if not _is_locked_error(delete_exc):
                    raise
                logger.warning(
                    "SQLite tenant %s: fallback DELETE temporaneamente occupato, "
                    "proseguo con la modalita' gia' attiva (%s)",
                    self.db_path,
                    delete_exc,
                )

    def _connect_readonly_immutable(self) -> sqlite3.Connection:
        db_uri = f"file:{self.db_path.resolve().as_posix()}?mode=ro&immutable=1"
        c = sqlite3.connect(
            db_uri,
            uri=True,
            timeout=30,
            check_same_thread=False,
        )
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA query_only=ON")
        c.execute("PRAGMA cache_size=-16000")
        c.execute("PRAGMA temp_store=MEMORY")
        return c

    def fetchall_readonly(self, sql: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        """Esegue una lettura senza tentare configurazioni scrivibili sui mount locali."""

        if not _requires_delete_journal_for_mount(self.db_path):
            return list(self.conn.execute(sql, parameters).fetchall())
        conn = self._connect_readonly_immutable()
        try:
            return list(conn.execute(sql, parameters).fetchall())
        finally:
            conn.close()

    # Tabelle che non hanno ancora dati_json nello schema originale.
    # ALTER TABLE ... ADD COLUMN è idempotente (fallisce silenziosamente se già esiste).
    _UPGRADE_ADD_DATI_JSON: tuple = (
        "fascicoli",
        "appuntamenti",
        "scadenze",
        "messaggi",
        "utenti",
    )
    _UPGRADE_ADD_COLUMNS: tuple[tuple[str, str, str], ...] = (
        ("fascicoli", "profilo_deposito_json", "TEXT DEFAULT '{}'"),
        ("preventivi_records", "profilo_deposito_json", "TEXT NOT NULL DEFAULT '{}'"),
        ("conferimenti_records", "profilo_deposito_json", "TEXT NOT NULL DEFAULT '{}'"),
    )

    def _schema_gia_pronto_su_connessione(self, conn: sqlite3.Connection) -> bool:
        required_tables = {
            "fascicoli",
            "clienti",
            "appuntamenti",
            "scadenze",
            "moduli_dati",
            "moduli_json_records",
            "settings_config",
        }
        tables = {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if not required_tables.issubset(tables):
            return False
        for table, column, _ddl in self._UPGRADE_ADD_COLUMNS:
            columns = {
                str(row[1])
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            if column not in columns:
                return False
        return True

    def _schema_gia_pronto(self) -> bool:
        if not self.db_path.exists() or self.db_path.stat().st_size <= 4096:
            return False
        try:
            uri = f"file:{self.db_path.as_posix()}?mode=ro&immutable=1"
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            try:
                return self._schema_gia_pronto_su_connessione(conn)
            finally:
                conn.close()
        except Exception:
            return False

    def _ensure_schema(self) -> None:
        """
        Crea il file DB, applica lo schema base e aggiunge le colonne
        dati_json alle tabelle che ne erano prive (upgrade schema idempotente).
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self._schema_gia_pronto():
            return
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(5):
            try:
                self._ensure_schema_once()
                return
            except sqlite3.OperationalError as exc:
                last_error = exc
                if not _is_locked_error(exc) or attempt == 4:
                    raise
                logger.warning(
                    "SQLite tenant %s: schema occupato, ritento (%s/5)",
                    self.db_path,
                    attempt + 2,
                )
                time.sleep(0.2 * (attempt + 1))
        if last_error is not None:
            raise last_error

    def _ensure_schema_once(self) -> None:
        conn = getattr(self._local, "_conn", None)
        if conn is None:
            conn = self._connect()
            self._local._conn = conn
        conn.executescript(_schema_sql())
        # Upgrade: aggiungi dati_json dove mancante
        for table in self._UPGRADE_ADD_DATI_JSON:
            try:
                conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN dati_json TEXT DEFAULT '{{}}'"
                )
            except Exception:
                pass  # colonna già presente — ok
        for table, column, ddl in self._UPGRADE_ADD_COLUMNS:
            try:
                existing = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            except Exception:
                pass
        self._backfill_deposit_profiles(conn)
        # Registra data creazione
        conn.execute(
            "INSERT OR IGNORE INTO _meta VALUES (?,?)",
            ("creato_il", __import__("datetime").datetime.now().isoformat()),
        )
        conn.commit()

    def _backfill_deposit_profiles(
        self,
        conn: sqlite3.Connection,
        *,
        verify_certificates: bool = False,
    ) -> None:
        """Popola i profili deposito mancanti sui record core esistenti."""
        try:
            from pct.deposito_profile_backfill import (
                CORE_DEPOSIT_PROFILE_TABLES,
                build_deposit_profile_for_record,
                deposit_profile_needs_update,
                merge_profile_into_payload,
            )
        except Exception as exc:
            logger.warning("Backfill profilo deposito non disponibile: %s", exc)
            return

        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        updated = 0
        for table, key_column in CORE_DEPOSIT_PROFILE_TABLES:
            if table not in tables:
                continue
            try:
                columns = {
                    row["name"]
                    for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
                }
            except Exception:
                continue
            if key_column not in columns or "profilo_deposito_json" not in columns:
                continue
            try:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            except Exception:
                continue
            for row in rows:
                row_dict = dict(row)
                record_key = str(row_dict.get(key_column) or "").strip()
                if not record_key:
                    continue
                try:
                    current = json.loads(row_dict.get("profilo_deposito_json") or "{}")
                    if not isinstance(current, dict):
                        current = {}
                except Exception:
                    current = {}
                try:
                    profile, payload = build_deposit_profile_for_record(
                        table,
                        row_dict,
                        verify_certificates=verify_certificates,
                    )
                except Exception as exc:
                    logger.warning(
                        "Backfill profilo deposito saltato per %s/%s: %s",
                        table,
                        record_key,
                        exc,
                    )
                    continue
                if not deposit_profile_needs_update(current, profile):
                    continue
                profile_json = json.dumps(profile, ensure_ascii=False)
                if "dati_json" in columns:
                    payload_json = json.dumps(
                        merge_profile_into_payload(payload, profile),
                        ensure_ascii=False,
                    )
                    conn.execute(
                        f"""
                        UPDATE {table}
                        SET profilo_deposito_json = ?, dati_json = ?
                        WHERE {key_column} = ?
                        """,
                        (profile_json, payload_json, record_key),
                    )
                else:
                    conn.execute(
                        f"UPDATE {table} SET profilo_deposito_json = ? WHERE {key_column} = ?",
                        (profile_json, record_key),
                    )
                updated += 1
        if updated:
            conn.execute(
                "INSERT OR REPLACE INTO _meta VALUES (?,?)",
                (
                    "profilo_deposito_backfill_il",
                    __import__("datetime").datetime.now().isoformat(),
                ),
            )
            logger.info("Backfill profilo deposito SQLite: %s record aggiornati", updated)

    def repair_deposit_profiles(self, *, verify_certificates: bool = False) -> None:
        """Riesegue il backfill profili deposito con opzioni esplicite."""
        conn = self.conn
        self._backfill_deposit_profiles(conn, verify_certificates=verify_certificates)
        conn.commit()

    def ensure_schema(self) -> None:
        """Riallinea lo schema SQLite corrente ai requisiti runtime."""

        conn = self.conn
        if not self._schema_gia_pronto_su_connessione(conn):
            self._ensure_schema_once()
            return
        self._backfill_deposit_profiles(conn)
        conn.commit()

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
        for attempt in range(_SQLITE_WRITE_ATTEMPTS):
            conn = self._conn_per_scrittura()
            began = False
            try:
                conn.execute(f"PRAGMA busy_timeout={_SQLITE_BUSY_TIMEOUT_MS}")
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
                if _is_readonly_write_error(exc):
                    self._close_thread_connection()
                    if attempt < _SQLITE_WRITE_ATTEMPTS - 1:
                        time.sleep(min(0.35 * (attempt + 1), 2.0))
                        continue
                if not _is_locked_error(exc) or attempt == _SQLITE_WRITE_ATTEMPTS - 1:
                    raise
                self._close_thread_connection()
                logger.warning(
                    "SQLite tenant %s: tabella %s occupata, ritento (%s/%s): %s",
                    self.db_path,
                    table,
                    attempt + 2,
                    _SQLITE_WRITE_ATTEMPTS,
                    exc,
                )
                time.sleep(min(0.35 * (attempt + 1), 2.0))
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
