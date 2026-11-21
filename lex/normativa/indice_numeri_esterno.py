"""Indice esterno dei numeri d'articolo per gli archivi normativi in sola lettura.

Gli archivi storici (edizione estesa, copia del server) non hanno l'indice dei numeri d'articolo e non si
possono modificare: la ricerca del solo numero su «Tutti gli atti» li avrebbe letti per intero (minuti). Qui si
prepara, fuori dalle richieste, un piccolo file SQLite accanto (``numeri-<impronta>.sqlite`` nella cartella
``IUSENTRA_BIBLIOTECA_NUMERI_DIR``) con il numero normalizzato da ``espressione_numero_articolo_sql``, la stessa
espressione dell'indice interno. Il file vale solo per la stessa versione dell'archivio (dimensione e data):
se l'archivio cambia, l'indice esterno non si usa più.

Uso: python -m lex.normativa.indice_numeri_esterno ARCHIVIO.sqlite [ARCHIVIO.sqlite ...] --cartella DIR
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from lex.normativa.biblioteca.identita import espressione_numero_articolo_sql

SCHEMA = "numeri"


def cartella() -> Path | None:
    valore = os.getenv("IUSENTRA_BIBLIOTECA_NUMERI_DIR", "").strip()
    return Path(valore) if valore else None


def _nome(archivio: Path) -> str:
    return "numeri-" + hashlib.sha256(str(archivio.resolve()).encode()).hexdigest()[:16] + ".sqlite"


def _stato(archivio: Path) -> tuple[int, int]:
    stato = archivio.stat()
    return stato.st_size, stato.st_mtime_ns


def indice_per(archivio: Path, base: Path | None = None) -> Path | None:
    """Il file dell'indice esterno valido per questa versione dell'archivio, se esiste."""
    base = base or cartella()
    if base is None:
        return None
    percorso = base / _nome(Path(archivio))
    if not percorso.is_file():
        return None
    try:
        with closing(sqlite3.connect(percorso.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
            riga = conn.execute("SELECT dimensione, mtime_ns FROM meta").fetchone()
    except sqlite3.Error:
        return None
    return percorso if riga and tuple(riga) == _stato(Path(archivio)) else None


def collega(connessione: sqlite3.Connection, archivio: Path) -> bool:
    """Collega l'indice esterno (schema «numeri») alla connessione dell'archivio, se c'è e vale."""
    percorso = indice_per(Path(archivio))
    if percorso is None:
        return False
    connessione.execute(f"ATTACH DATABASE ? AS {SCHEMA}", (percorso.resolve().as_uri() + "?mode=ro",))
    return True


def prepara(archivio: Path, base: Path, *, blocco: int = 20000, pausa: float = 0.0) -> Path:
    """Scrive l'indice esterno per l'archivio (lettura in sola lettura, a blocchi, con pausa per non saturare)."""
    archivio = Path(archivio)
    base.mkdir(parents=True, exist_ok=True)
    finale = base / _nome(archivio)
    provvisorio = finale.with_suffix(".provvisorio")
    provvisorio.unlink(missing_ok=True)
    dimensione, mtime = _stato(archivio)
    espressione = espressione_numero_articolo_sql()
    with closing(sqlite3.connect(archivio.resolve().as_uri() + "?mode=ro", uri=True)) as sorgente, \
            closing(sqlite3.connect(provvisorio)) as uscita:
        # con_testo: la stessa condizione di TESTO_PRESENTE, calcolata qui una volta: la ricerca non legge i testi.
        uscita.execute("CREATE TABLE numeri_articolo(article_id INTEGER PRIMARY KEY, document_id INTEGER, numero TEXT, "
                       "con_testo INTEGER)")
        uscita.execute("CREATE TABLE meta(sorgente TEXT, dimensione INTEGER, mtime_ns INTEGER, creato TEXT, righe INTEGER)")
        ultimo, righe = 0, 0
        while True:
            parte = sorgente.execute(
                f"SELECT id, document_id, {espressione}, "
                "(octet_length(article_text)>0 AND (octet_length(article_text)>256 OR length(trim(article_text))>0)) "
                "FROM normative_articles WHERE id>? ORDER BY id LIMIT ?",
                (ultimo, blocco)).fetchall()
            if not parte:
                break
            uscita.executemany("INSERT INTO numeri_articolo VALUES (?,?,?,?)", parte)
            ultimo, righe = parte[-1][0], righe + len(parte)
            if pausa:
                time.sleep(pausa)
        uscita.execute("CREATE INDEX idx_numeri_numero ON numeri_articolo(numero, con_testo, article_id)")
        uscita.execute("INSERT INTO meta VALUES (?,?,?,?,?)",
                       (str(archivio), dimensione, mtime, time.strftime("%Y-%m-%dT%H:%M:%S"), righe))
        uscita.commit()
    if _stato(archivio) != (dimensione, mtime):
        provvisorio.unlink(missing_ok=True)
        raise RuntimeError(f"{archivio} è cambiato durante la preparazione: indice non pubblicato")
    os.replace(provvisorio, finale)
    return finale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("archivi", nargs="+")
    ap.add_argument("--cartella", required=True)
    ap.add_argument("--pausa", type=float, default=0.05)
    args = ap.parse_args()
    for archivio in args.archivi:
        inizio = time.monotonic()
        print(f"{archivio}: preparazione…", flush=True)
        percorso = prepara(Path(archivio), Path(args.cartella), pausa=args.pausa)
        print(f"{archivio}: {percorso} in {time.monotonic() - inizio:.0f} s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
