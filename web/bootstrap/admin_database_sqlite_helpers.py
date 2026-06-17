"""Helper SQLite per le route amministrative database."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    if n < 1024 ** 3:
        return f"{n / 1024 ** 2:.1f} MB"
    return f"{n / 1024 ** 3:.1f} GB"


def ottimizza_sqlite_file(percorso_db: str, modulo: str) -> dict:
    target = Path(percorso_db)
    before = target.stat().st_size if target.exists() and target.is_file() else 0
    if not target.exists() or not target.is_file():
        return {
            "modulo": modulo,
            "operazione": "Ottimizzazione SQL",
            "ok": False,
            "riuscita": False,
            "messaggio": "Archivio SQL non trovato.",
            "dettagli": "Archivio SQL non trovato.",
            "ms": 0,
            "bytes_prima": before,
            "bytes_dopo": before,
            "risparmio_bytes": 0,
            "risparmio_pct": 0,
        }
    started = datetime.now()
    try:
        conn = sqlite3.connect(str(target), isolation_level=None)
        try:
            conn.execute("PRAGMA optimize")
            conn.execute("ANALYZE")
            conn.execute("VACUUM")
        finally:
            conn.close()
        after = target.stat().st_size
        saved = max(before - after, 0)
        return {
            "modulo": modulo,
            "operazione": "VACUUM + ANALYZE + PRAGMA optimize",
            "ok": True,
            "riuscita": True,
            "messaggio": "Archivio SQL ottimizzato.",
            "dettagli": f"{fmt_bytes(before)} -> {fmt_bytes(after)}",
            "ms": int((datetime.now() - started).total_seconds() * 1000),
            "bytes_prima": before,
            "bytes_dopo": after,
            "risparmio_bytes": saved,
            "risparmio_pct": round((saved / before) * 100, 1) if before else 0,
        }
    except Exception as exc:
        after = target.stat().st_size if target.exists() else before
        return {
            "modulo": modulo,
            "operazione": "Ottimizzazione SQL",
            "ok": False,
            "riuscita": False,
            "messaggio": "Ottimizzazione SQL non completata.",
            "dettagli": str(exc),
            "ms": int((datetime.now() - started).total_seconds() * 1000),
            "bytes_prima": before,
            "bytes_dopo": after,
            "risparmio_bytes": 0,
            "risparmio_pct": 0,
        }
