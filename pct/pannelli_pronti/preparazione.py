"""Preparazione governata dei contatori di revisione: backup verificato, trigger, conferma.

Si esegue fuori dalle richieste (rilascio, ``scripts/pannelli_pronti_prepara.py``). Il backup verificato si fa
solo quando il piano dei trigger cambia (prima installazione, tabella nuova, versione nuova); a piano invariato
non si scrive nulla.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from pct.pannelli_pronti import revisioni


def _apri(percorso: str) -> sqlite3.Connection:
    conn = sqlite3.connect(percorso, timeout=60, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=60000")
    return conn


def da_preparare(percorso: str, tabelle_senza_fascicolo: Iterable[str] = ()) -> bool:
    conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=30)
    try:
        piano = revisioni.piano_trigger(conn, tabelle_senza_fascicolo)
        firma = revisioni.firma_piano(piano)
        return revisioni.stato(conn) != firma
    finally:
        conn.close()


def prepara_database(percorso: str, *, tabelle_senza_fascicolo: Iterable[str] = (), backup_dir: str | Path | None,
                     applica: bool) -> dict[str, object]:
    """Installa o riallinea i trigger di un database dello studio. Senza ``applica`` dice solo che cosa farebbe."""
    tabelle = tuple(tabelle_senza_fascicolo)
    if not Path(percorso).is_file():
        return {"database": percorso, "presente": False, "cambiato": False}
    if not da_preparare(percorso, tabelle):
        return {"database": percorso, "presente": True, "cambiato": False}
    if not applica:
        return {"database": percorso, "presente": True, "cambiato": False, "da_preparare": True}
    if backup_dir is None:
        raise ValueError("Serve una cartella di backup persistente per preparare i contatori.")
    from scripts.query_index_backup import verified_backup

    conn = _apri(percorso)
    try:
        firma = revisioni.firma_piano(revisioni.piano_trigger(conn, tabelle))
        # Un backup per piano: a ogni nuovo piano una copia nuova (il manifest esistente vale solo per il suo piano).
        verified_backup(SimpleNamespace(conn=conn, db_path=percorso, backend_kind="sqlite"),
                        Path(backup_dir) / f"{Path(percorso).stem}-{firma[:16]}")
        conn.execute("BEGIN IMMEDIATE")
        try:
            esito = revisioni.installa(conn, tabelle)
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()
    return {"database": percorso, "presente": True, **esito}
