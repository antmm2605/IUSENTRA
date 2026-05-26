"""Banca dati locale dei Comuni italiani.

La base SQLite viene generata dagli script in `scripts/` a partire da fonti web
documentate: ISTAT per l'elenco ufficiale dei Comuni e Garda Informatica per i
CAP in licenza MIT.
"""

from __future__ import annotations

import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_TERRITORIO_DB = Path(__file__).resolve().parent / "data" / "territorio_italia.sqlite"


@dataclass(frozen=True)
class ComuneItalia:
    codice_istat: str
    nome: str
    nome_altro: str
    cap: tuple[str, ...]
    sigla_provincia: str
    provincia: str
    codice_regione: str
    regione: str
    codice_belfiore: str
    lat: str
    lon: str

    @property
    def label(self) -> str:
        return f"{self.nome} ({self.sigla_provincia})"

    @property
    def giustizia_map_value(self) -> str:
        return f"{self.codice_regione}{self.codice_istat}#{self.nome}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "codiceIstat": self.codice_istat,
            "nome": self.nome,
            "nomeAltro": self.nome_altro,
            "label": self.label,
            "cap": list(self.cap),
            "siglaProvincia": self.sigla_provincia,
            "provincia": self.provincia,
            "codiceRegione": self.codice_regione,
            "regione": self.regione,
            "codiceBelfiore": self.codice_belfiore,
            "lat": self.lat,
            "lon": self.lon,
            "giustiziaMapValue": self.giustizia_map_value,
        }


def territorio_db_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path or os.getenv("IUSENTRA_TERRITORIO_DB") or DEFAULT_TERRITORIO_DB)


def normalize_comune_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _row_to_comune(row: sqlite3.Row) -> ComuneItalia:
    cap_raw = str(row["cap"] or "")
    return ComuneItalia(
        codice_istat=str(row["codice_istat"] or ""),
        nome=str(row["nome"] or ""),
        nome_altro=str(row["nome_altro"] or ""),
        cap=tuple(item for item in cap_raw.split(",") if item),
        sigla_provincia=str(row["sigla_provincia"] or ""),
        provincia=str(row["provincia"] or ""),
        codice_regione=str(row["codice_regione"] or ""),
        regione=str(row["regione"] or ""),
        codice_belfiore=str(row["codice_belfiore"] or ""),
        lat=str(row["lat"] or ""),
        lon=str(row["lon"] or ""),
    )


def _connect(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    path = territorio_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def search_comuni(query: str, *, limit: int = 20, db_path: str | os.PathLike[str] | None = None) -> list[ComuneItalia]:
    key = normalize_comune_key(query)
    if len(key) < 2:
        return []
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM comuni
            WHERE search_key LIKE ?
               OR codice_istat = ?
               OR codice_belfiore = ?
               OR cap LIKE ?
            ORDER BY
              CASE WHEN search_key = ? THEN 0 WHEN search_key LIKE ? THEN 1 ELSE 2 END,
              nome COLLATE NOCASE,
              sigla_provincia
            LIMIT ?
            """,
            (f"%{key}%", key, key.upper(), f"%{query.strip()}%", key, f"{key}%", int(limit)),
        ).fetchall()
    return [_row_to_comune(row) for row in rows]


def get_comune(
    *,
    codice_istat: str = "",
    nome: str = "",
    db_path: str | os.PathLike[str] | None = None,
) -> ComuneItalia | None:
    with _connect(db_path) as conn:
        row = None
        if codice_istat:
            row = conn.execute("SELECT * FROM comuni WHERE codice_istat = ?", (str(codice_istat).strip(),)).fetchone()
        if row is None and nome:
            key = normalize_comune_key(nome)
            row = conn.execute(
                """
                SELECT *
                FROM comuni
                WHERE search_key = ?
                ORDER BY nome COLLATE NOCASE
                LIMIT 1
                """,
                (key,),
            ).fetchone()
    return _row_to_comune(row) if row is not None else None


def territorio_stats(db_path: str | os.PathLike[str] | None = None) -> dict[str, int]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
              COUNT(*) AS comuni,
              SUM(CASE WHEN cap <> '' THEN 1 ELSE 0 END) AS comuni_con_cap,
              COUNT(DISTINCT sigla_provincia) AS province,
              COUNT(DISTINCT codice_regione) AS regioni
            FROM comuni
            """
        ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}
