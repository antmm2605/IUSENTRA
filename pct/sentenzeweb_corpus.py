"""Read-only owner of the shared public SentenzeWeb corpus."""

import os
import sqlite3
from pathlib import Path

from pct.giurisprudenza_corpus import _COLONNE_RICERCA, GestioneCorpusGiurisprudenza


class PublicSentenzeWebCorpus(GestioneCorpusGiurisprudenza):
    def __init__(self, path):
        self.db_path = str(Path(path).resolve(strict=True))
        with self._connect() as connection:
            foreign_sources = connection.execute(
                "SELECT count(*) FROM fonti_giurisprudenza WHERE codice != ?", ("cassazione_sentenzeweb",)
            ).fetchone()[0]
            if foreign_sources:
                raise ValueError("The shared corpus contains sources outside its public owner")

    def recent_acquisitions(self, limit=10):
        """Bounded initial list; this is acquisition order, not relevance ranking."""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT {_COLONNE_RICERCA} FROM sentenze s ORDER BY s.id DESC LIMIT ?",
                (max(1, min(int(limit), 50)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self):
        connection = sqlite3.connect(Path(self.db_path).as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only=ON")
        return connection


def configured_corpus(config=None):
    config = config or {}
    directory = str(
        config.get("IUSENTRA_SENTENZEWEB_DIRECTORY") or os.getenv("IUSENTRA_SENTENZEWEB_DIRECTORY") or ""
    ).strip()
    path = Path(directory) / "giurisprudenza_corpus.db" if directory else None
    return PublicSentenzeWebCorpus(path) if path and path.is_file() else None
