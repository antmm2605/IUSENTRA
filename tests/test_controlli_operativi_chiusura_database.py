"""I controlli operativi chiudono i database temporanei che aprono (verifica del 24/11/2026 sull'8080).

Dopo il controllo del mattino lo scheduler teneva aperti oltre cento descrittori su
``/tmp/iusentra-crash-*/studio.db`` già cancellati: le istanze di ``StudioDB`` restavano nella cache del processo,
con una connessione per ogni thread che le aveva usate.
"""

from __future__ import annotations

import sqlite3
import threading

import pytest

from pct import storage
from pct.operational_resilience import _cartella_di_controllo
from pct.storage import StudioDB


def _connessione_da_altro_thread(db: StudioDB) -> sqlite3.Connection:
    trovata: list[sqlite3.Connection] = []
    thread = threading.Thread(target=lambda: trovata.append(db.conn))
    thread.start()
    thread.join(10)
    return trovata[0]


def _chiusa(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return True
    return False


def test_la_cartella_del_controllo_chiude_i_database_di_tutti_i_thread():
    with _cartella_di_controllo(prefix="iusentra-crash-prova-") as tmp:
        db = StudioDB.get(f"{tmp}/studio.db")
        mia = db.conn
        altra = _connessione_da_altro_thread(db)
        assert mia is not altra
        chiave = str(db.db_path)
        assert chiave in storage._instances
    assert chiave not in storage._instances
    assert _chiusa(mia) and _chiusa(altra)


def test_invalidate_sotto_tocca_solo_la_cartella_indicata(tmp_path):
    dentro = StudioDB.get(str(tmp_path / "controllo" / "studio.db"))
    fuori = StudioDB.get(str(tmp_path / "studio_vero" / "studio.db"))
    conn_dentro, conn_fuori = dentro.conn, fuori.conn
    try:
        assert StudioDB.invalidate_sotto(tmp_path / "controllo") == 1
        assert _chiusa(conn_dentro)
        assert not _chiusa(conn_fuori)
        assert str(fuori.db_path) in storage._instances
    finally:
        StudioDB.invalidate(str(fuori.db_path))


def test_la_cartella_si_chiude_anche_se_il_controllo_fallisce():
    with pytest.raises(RuntimeError):
        with _cartella_di_controllo(prefix="iusentra-crash-prova-") as tmp:
            db = StudioDB.get(f"{tmp}/studio.db")
            conn = db.conn
            raise RuntimeError("controllo fallito")
    assert _chiusa(conn)
    assert not any(k.startswith(tmp) for k in storage._instances)
