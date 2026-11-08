"""Archivio condiviso delle Notizie utili (SQLite, accanto agli archivi delle fonti ufficiali).

Le notizie sono pubbliche e uguali per tutti gli studi: si acquisiscono una volta
sola. Letture, preferiti e collegamenti ai fascicoli restano nel database dello
studio (`web/blueprints/api_v1_react.py`, sezione per utente).
La deduplica è per identificativo (fonte + collegamento ufficiale): una notizia
ripubblicata aggiorna titolo e sintesi ma conserva la data di acquisizione.
"""

from __future__ import annotations

from contextlib import closing
from datetime import date, timedelta
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

CONSERVAZIONE_GIORNI = 365

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS notizie (
        id TEXT PRIMARY KEY,
        fonte TEXT NOT NULL,
        etichetta_fonte TEXT NOT NULL,
        ente TEXT NOT NULL,
        titolo TEXT NOT NULL,
        url TEXT NOT NULL,
        data TEXT NOT NULL,
        sintesi TEXT NOT NULL DEFAULT '',
        tipo TEXT NOT NULL,
        materia TEXT NOT NULL DEFAULT '',
        atti_json TEXT NOT NULL DEFAULT '[]',
        riferimento_ufficiale TEXT NOT NULL DEFAULT '',
        acquisita_il TEXT NOT NULL,
        aggiornata_il TEXT NOT NULL,
        inoltrata_revisione INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS notizie_data ON notizie (data DESC, titolo)",
    "CREATE INDEX IF NOT EXISTS notizie_fonte ON notizie (fonte, data DESC)",
    """
    CREATE TABLE IF NOT EXISTS fonti_stato (
        fonte TEXT PRIMARY KEY,
        ultimo_tentativo TEXT NOT NULL,
        ultimo_esito_ok INTEGER NOT NULL,
        ultimo_successo TEXT NOT NULL DEFAULT '',
        messaggio TEXT NOT NULL DEFAULT '',
        voci INTEGER NOT NULL DEFAULT 0,
        ultima_pubblicazione TEXT NOT NULL DEFAULT ''
    )
    """,
)
_CAMPI = (
    "id", "fonte", "etichetta_fonte", "ente", "titolo", "url", "data", "sintesi", "tipo", "materia",
    "riferimento_ufficiale",
)


class ArchivioNotiziario:
    def __init__(self, percorso: str | Path, *, sola_lettura: bool = False):
        self.percorso = Path(percorso)
        self.sola_lettura = sola_lettura
        if not sola_lettura:
            self.percorso.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connetti()) as conn:
                for istruzione in _SCHEMA:
                    conn.execute(istruzione)
                conn.commit()

    @classmethod
    def in_lettura(cls, percorso: str | Path) -> "ArchivioNotiziario | None":
        """Archivio aperto in sola lettura, o None se non è ancora stato creato dal giro delle fonti."""
        return cls(percorso, sola_lettura=True) if Path(percorso).is_file() else None

    def _connetti(self) -> sqlite3.Connection:
        if self.sola_lettura:
            conn = sqlite3.connect(f"file:{self.percorso}?mode=ro", uri=True, timeout=10)
        else:
            conn = sqlite3.connect(str(self.percorso), timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def salva(self, notizie: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Inserisce o aggiorna; restituisce le notizie che l'archivio non aveva."""
        nuove: list[dict[str, Any]] = []
        with closing(self._connetti()) as conn:
            for voce in notizie:
                esistente = conn.execute("SELECT id FROM notizie WHERE id = ?", (voce["id"],)).fetchone()
                valori = [str(voce.get(campo) or "") for campo in _CAMPI]
                atti = json.dumps(list(voce.get("atti") or []), ensure_ascii=False)
                adesso = str(voce.get("acquisita_il") or "")
                if esistente:
                    conn.execute(
                        "UPDATE notizie SET " + ", ".join(f"{campo} = ?" for campo in _CAMPI[1:])
                        + ", atti_json = ?, aggiornata_il = ? WHERE id = ?",
                        (*valori[1:], atti, adesso, voce["id"]),
                    )
                    continue
                conn.execute(
                    "INSERT INTO notizie (" + ", ".join(_CAMPI) + ", atti_json, acquisita_il, aggiornata_il) "
                    "VALUES (" + ", ".join("?" for _ in _CAMPI) + ", ?, ?, ?)",
                    (*valori, atti, adesso, adesso),
                )
                nuove.append(voce)
            conn.commit()
        return nuove

    def registra_esito(self, fonte: str, *, ok: bool, quando: str, messaggio: str = "", voci: int = 0) -> None:
        with closing(self._connetti()) as conn:
            ultima = conn.execute("SELECT MAX(data) FROM notizie WHERE fonte = ?", (fonte,)).fetchone()[0] or ""
            precedente = conn.execute("SELECT ultimo_successo FROM fonti_stato WHERE fonte = ?", (fonte,)).fetchone()
            successo = quando if ok else (precedente["ultimo_successo"] if precedente else "")
            conn.execute(
                """
                INSERT INTO fonti_stato (fonte, ultimo_tentativo, ultimo_esito_ok, ultimo_successo, messaggio, voci, ultima_pubblicazione)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fonte) DO UPDATE SET
                    ultimo_tentativo = excluded.ultimo_tentativo, ultimo_esito_ok = excluded.ultimo_esito_ok,
                    ultimo_successo = excluded.ultimo_successo, messaggio = excluded.messaggio,
                    voci = excluded.voci, ultima_pubblicazione = excluded.ultima_pubblicazione
                """,
                (fonte, quando, 1 if ok else 0, successo, messaggio, int(voci), ultima),
            )
            conn.commit()

    def stato_fonti(self) -> dict[str, dict[str, Any]]:
        with closing(self._connetti()) as conn:
            righe = conn.execute("SELECT * FROM fonti_stato").fetchall()
            conteggi = dict(conn.execute("SELECT fonte, COUNT(*) FROM notizie GROUP BY fonte").fetchall())
        return {
            riga["fonte"]: {**dict(riga), "ultimo_esito_ok": bool(riga["ultimo_esito_ok"]), "in_archivio": int(conteggi.get(riga["fonte"], 0))}
            for riga in righe
        }

    def elenco(self, *, limite: int = 800) -> list[dict[str, Any]]:
        """Notizie più recenti per data di pubblicazione."""
        with closing(self._connetti()) as conn:
            righe = conn.execute(
                "SELECT * FROM notizie ORDER BY data DESC, acquisita_il DESC, titolo LIMIT ?", (int(limite),)
            ).fetchall()
        return [_riga(riga) for riga in righe]

    def notizia(self, notizia_id: str) -> dict[str, Any] | None:
        with closing(self._connetti()) as conn:
            riga = conn.execute("SELECT * FROM notizie WHERE id = ?", (notizia_id,)).fetchone()
        return _riga(riga) if riga else None

    def da_inoltrare(self, fonti: Iterable[str], *, limite: int = 200) -> list[dict[str, Any]]:
        codici = list(fonti)
        if not codici:
            return []
        with closing(self._connetti()) as conn:
            righe = conn.execute(
                "SELECT * FROM notizie WHERE inoltrata_revisione = 0 AND tipo IN ('norma', 'pronuncia', 'prassi') "
                "AND fonte IN (" + ", ".join("?" for _ in codici) + ") ORDER BY data DESC LIMIT ?",
                (*codici, int(limite)),
            ).fetchall()
        return [_riga(riga) for riga in righe]

    def segna_inoltrate(self, ids: Iterable[str]) -> None:
        elenco = list(ids)
        if not elenco:
            return
        with closing(self._connetti()) as conn:
            conn.executemany("UPDATE notizie SET inoltrata_revisione = 1 WHERE id = ?", [(i,) for i in elenco])
            conn.commit()

    def pota(self, *, oggi: date, giorni: int = CONSERVAZIONE_GIORNI) -> int:
        limite = (oggi - timedelta(days=giorni)).isoformat()
        with closing(self._connetti()) as conn:
            cancellate = conn.execute("DELETE FROM notizie WHERE data < ?", (limite,)).rowcount
            conn.commit()
        return int(cancellate or 0)


def _riga(riga: sqlite3.Row) -> dict[str, Any]:
    voce = dict(riga)
    try:
        voce["atti"] = list(json.loads(voce.pop("atti_json") or "[]"))
    except (TypeError, ValueError):
        voce["atti"] = []
    voce["inoltrata_revisione"] = bool(voce.get("inoltrata_revisione"))
    return voce


__all__ = ["ArchivioNotiziario", "CONSERVAZIONE_GIORNI"]
