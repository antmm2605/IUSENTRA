"""Coda di revisione Lex locale, indicizzata e pubblicata in una transazione."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Iterable

NOME_ARCHIVIO = "qa_review_queue.sqlite"

_SCHEMA = """
    CREATE TABLE IF NOT EXISTS candidati (
        qa_id TEXT PRIMARY KEY,
        stato TEXT NOT NULL CHECK(stato IN ('pending', 'approved', 'rejected')),
        contenuto_json TEXT NOT NULL,
        generazione INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS candidati_visibili ON candidati(generazione, stato, qa_id);
    CREATE TABLE IF NOT EXISTS coda_attiva (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        generazione INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS contatori_coda (
        generazione INTEGER NOT NULL,
        stato TEXT NOT NULL,
        numero INTEGER NOT NULL CHECK(numero >= 0),
        PRIMARY KEY(generazione, stato)
    );
    CREATE TABLE IF NOT EXISTS revisioni (
        id INTEGER PRIMARY KEY,
        qa_id TEXT NOT NULL REFERENCES candidati(qa_id),
        stato TEXT NOT NULL,
        revisore TEXT NOT NULL,
        revisionata_il TEXT NOT NULL
    );
"""


def _scrittura(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=20)
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _revisioni_precedenti(path: Path) -> Iterable[tuple[str, str, str]]:
    legacy = path.with_suffix(".json")
    if not legacy.is_file():
        return
    raw = json.loads(legacy.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else next(
        (raw[k] for k in ("items", "qa_pairs", "pairs", "rows") if isinstance(raw.get(k), list)), [],
    )
    for row in rows:
        if not isinstance(row, dict):
            continue
        qa_id = row.get("qa_id") or row.get("id")
        stato = str(row.get("review_status") or row.get("status") or "").lower()
        if stato in {"approvata", "approvato"}:
            stato = "approved"
        if stato in {"scartata", "scartato"}:
            stato = "rejected"
        if qa_id and stato in {"approved", "rejected"}:
            yield str(qa_id), stato, json.dumps({**row, "review_status": stato}, ensure_ascii=False)


_CONTA_CANDIDATI = """
    SELECT stato, COUNT(*) FROM candidati WHERE generazione=? GROUP BY stato
"""


def _salva_contatori(conn: sqlite3.Connection, generazione: int) -> None:
    conn.execute("DELETE FROM contatori_coda")
    conn.execute(
        "INSERT INTO contatori_coda SELECT ?, stato, COUNT(*) FROM candidati "
        "WHERE generazione=? GROUP BY stato",
        (generazione, generazione),
    )
    # Conserva il riferimento alla generazione anche se la coda è vuota.
    conn.execute("INSERT INTO contatori_coda VALUES (?, '', 0)", (generazione,))


def riallinea_contatori(path: Path) -> None:
    """Materializza una volta i contatori delle code già pubblicate."""
    with closing(_scrittura(path)) as conn:
        conn.executescript(_SCHEMA)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT generazione FROM coda_attiva WHERE singleton=1").fetchone()
            if row and not conn.execute(
                "SELECT 1 FROM contatori_coda WHERE generazione=? AND stato=''", row,
            ).fetchone():
                _salva_contatori(conn, row[0])


def pubblica(path: Path, candidati: Iterable[dict[str, Any]]) -> None:
    with closing(_scrittura(path)) as conn:
        conn.executescript(_SCHEMA)
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT generazione FROM coda_attiva WHERE singleton=1").fetchone()
            generazione = (int(row[0]) if row else 0) + 1
            if row is None:
                conn.executemany(
                    "INSERT OR IGNORE INTO candidati VALUES (?, ?, ?, 0)",
                    _revisioni_precedenti(path),
                )
            conn.executemany(
                """
                INSERT INTO candidati(qa_id, stato, contenuto_json, generazione)
                VALUES (?, 'pending', ?, ?)
                ON CONFLICT(qa_id) DO UPDATE SET
                    generazione=excluded.generazione,
                    contenuto_json=CASE WHEN candidati.stato='pending'
                        THEN excluded.contenuto_json ELSE candidati.contenuto_json END
                """,
                (
                    (str(row["qa_id"]), json.dumps(row, ensure_ascii=False), generazione)
                    for row in candidati
                ),
            )
            _salva_contatori(conn, generazione)
            conn.execute(
                "INSERT INTO coda_attiva VALUES (1, ?) ON CONFLICT(singleton) DO UPDATE SET generazione=excluded.generazione",
                (generazione,),
            )


def leggi(path: Path, *, limite: int = 0) -> tuple[dict[str, int], list[dict[str, Any]]]:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as conn:
        conn.execute("BEGIN")
        active = conn.execute("SELECT generazione FROM coda_attiva WHERE singleton=1").fetchone()
        if active is None:
            return {}, []
        has_counts = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='contatori_coda'"
        ).fetchone()
        counts = dict(conn.execute(
            "SELECT stato, numero FROM contatori_coda WHERE generazione=?", active,
        )) if has_counts else {}
        if "" in counts:
            counts = {stato: numero for stato, numero in counts.items() if stato and numero}
        else:
            counts = dict(conn.execute(_CONTA_CANDIDATI, active))
        rows = conn.execute(
            """
            SELECT contenuto_json FROM candidati WHERE stato='pending'
            AND generazione=(SELECT generazione FROM coda_attiva WHERE singleton=1)
            ORDER BY qa_id LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return counts, [json.loads(row[0]) for row in rows]


def revisiona(
    path: Path, qa_id: str, modifica: Callable[[dict[str, Any]], dict[str, Any] | None],
) -> dict[str, Any] | None:
    with closing(_scrittura(path)) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT contenuto_json, stato, generazione FROM candidati WHERE qa_id=?
            AND generazione=(SELECT generazione FROM coda_attiva WHERE singleton=1)
            """,
            (qa_id,),
        ).fetchone()
        if not row:
            return None
        aggiornato = modifica(json.loads(row[0]))
        if aggiornato is None:
            return None
        stato = aggiornato["review_status"]
        conn.execute(
            "UPDATE candidati SET stato=?, contenuto_json=? WHERE qa_id=?",
            (stato, json.dumps(aggiornato, ensure_ascii=False), qa_id),
        )
        precedente, generazione = row[1:]
        if stato != precedente and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='contatori_coda'"
        ).fetchone() and conn.execute(
            "SELECT 1 FROM contatori_coda WHERE generazione=? AND stato=''", (generazione,),
        ).fetchone():
            conn.execute(
                "UPDATE contatori_coda SET numero=numero-1 WHERE generazione=? AND stato=?",
                (generazione, precedente),
            )
            conn.execute(
                "INSERT INTO contatori_coda VALUES (?, ?, 1) "
                "ON CONFLICT(generazione, stato) DO UPDATE SET numero=numero+1",
                (generazione, stato),
            )
        conn.execute(
            "INSERT INTO revisioni(qa_id, stato, revisore, revisionata_il) VALUES (?, ?, ?, ?)",
            (qa_id, stato, aggiornato["reviewer_id"], aggiornato["reviewed_at"]),
        )
    return aggiornato
