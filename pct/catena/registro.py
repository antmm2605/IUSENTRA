"""Registro dei controlli del guardiano della catena: ogni giro, ogni incoerenza, ogni riparazione con il motivo.

SQLite in ``<studio>/intelligence/guardiano_catena.sqlite``: fuori da ``studio.db`` e dal registro delle letture,
quindi le scritture del registro non cambiano l'impronta delle fonti e non riaccendono la catena (niente cicli).
Una riparazione si registra, non si cancella (art. 20 CAD): lo stato di un'incoerenza passa da «aperta» a
«riparata» o «avviso» e, quando non si ripresenta più, a «chiusa».
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

NOME_FILE = "guardiano_catena.sqlite"
APERTA, RIPARATA, AVVISO, CHIUSA = "aperta", "riparata", "avviso", "chiusa"
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS giri (
        id INTEGER PRIMARY KEY AUTOINCREMENT, fascicolo_id TEXT NOT NULL, quando TEXT NOT NULL, origine TEXT NOT NULL,
        impronta TEXT NOT NULL DEFAULT '', esito TEXT NOT NULL, incoerenze INTEGER NOT NULL DEFAULT 0,
        riparate INTEGER NOT NULL DEFAULT 0, avvisi INTEGER NOT NULL DEFAULT 0, versione TEXT NOT NULL DEFAULT '')""",
    "CREATE INDEX IF NOT EXISTS giri_fascicolo ON giri(fascicolo_id, id)",
    """CREATE TABLE IF NOT EXISTS incoerenze (
        fascicolo_id TEXT NOT NULL, chiave TEXT NOT NULL, codice TEXT NOT NULL, stato TEXT NOT NULL,
        descrizione TEXT NOT NULL, perche TEXT NOT NULL, norma TEXT NOT NULL DEFAULT '', riparazione TEXT NOT NULL DEFAULT '',
        esito_riparazione TEXT NOT NULL DEFAULT '', tentativi INTEGER NOT NULL DEFAULT 0, dati TEXT NOT NULL DEFAULT '{}',
        prima_vista TEXT NOT NULL, ultima_vista TEXT NOT NULL, chiusa_il TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (fascicolo_id, chiave))""",
    "CREATE INDEX IF NOT EXISTS incoerenze_stato ON incoerenze(stato, codice)",
)
# Dopo due riparazioni non riuscite la stessa incoerenza diventa un avviso: la regola non basta.
TENTATIVI_MASSIMI = 2


def adesso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def percorso(data_paths: dict[str, Any]) -> Path | None:
    """Accanto agli altri archivi «intelligence» dello studio (come le bozze dei passi)."""
    studio_db = str((data_paths or {}).get("STUDIO_DB") or "")
    return Path(studio_db).parent / "intelligence" / NOME_FILE if studio_db else None


class RegistroGuardiano:
    def __init__(self, file: str | Path) -> None:
        self.file = Path(file)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.file), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            for istruzione in _SCHEMA:
                conn.execute(istruzione)
            yield conn
            conn.commit()
        finally:
            conn.close()

    def tentativi(self, fascicolo_id: str, chiave: str) -> int:
        if not self.file.exists():
            return 0
        with self._conn() as conn:
            riga = conn.execute("SELECT tentativi FROM incoerenze WHERE fascicolo_id=? AND chiave=?",
                                (fascicolo_id, chiave)).fetchone()
        return int(riga["tentativi"]) if riga else 0

    def registra_giro(self, fascicolo_id: str, *, origine: str, impronta: str, esito: str,
                      voci: list[dict[str, Any]], versione: str) -> dict[str, int]:
        """Registra il giro e lo stato di ogni incoerenza; chiude quelle che non si sono ripresentate."""
        quando = adesso()
        conteggi = {"incoerenze": len(voci), "riparate": 0, "avvisi": 0}
        with self._conn() as conn:
            viste = set()
            for voce in voci:
                viste.add(voce["chiave"])
                stato = RIPARATA if voce.get("esito_riparazione", "").startswith("riparata") else AVVISO if not voce.get(
                    "riparazione") or voce.get("avviso") else APERTA
                if stato == RIPARATA:
                    conteggi["riparate"] += 1
                elif stato == AVVISO:
                    conteggi["avvisi"] += 1
                conn.execute(
                    """INSERT INTO incoerenze(fascicolo_id, chiave, codice, stato, descrizione, perche, norma, riparazione,
                           esito_riparazione, tentativi, dati, prima_vista, ultima_vista)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(fascicolo_id, chiave) DO UPDATE SET stato=excluded.stato, descrizione=excluded.descrizione,
                           perche=excluded.perche, norma=excluded.norma, riparazione=excluded.riparazione,
                           esito_riparazione=excluded.esito_riparazione, tentativi=incoerenze.tentativi+excluded.tentativi,
                           dati=excluded.dati, ultima_vista=excluded.ultima_vista, chiusa_il=''""",
                    (fascicolo_id, voce["chiave"], voce["codice"], stato, voce["descrizione"], voce["perche"],
                     voce.get("norma") or "", voce.get("riparazione") or "", voce.get("esito_riparazione") or "",
                     1 if voce.get("riparazione") and not voce.get("avviso") else 0,
                     json.dumps(voce.get("dati") or {}, ensure_ascii=False, default=str), quando, quando))
            if esito != "in_aggiornamento":
                righe = conn.execute("SELECT chiave FROM incoerenze WHERE fascicolo_id=? AND stato!=?",
                                     (fascicolo_id, CHIUSA)).fetchall()
                for riga in righe:
                    if riga["chiave"] not in viste:
                        conn.execute("UPDATE incoerenze SET stato=?, chiusa_il=? WHERE fascicolo_id=? AND chiave=?",
                                     (CHIUSA, quando, fascicolo_id, riga["chiave"]))
            conn.execute(
                "INSERT INTO giri(fascicolo_id, quando, origine, impronta, esito, incoerenze, riparate, avvisi, versione) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (fascicolo_id, quando, origine, impronta or "", esito, len(voci), conteggi["riparate"], conteggi["avvisi"],
                 versione))
        return conteggi

    def avvisi(self, fascicolo_id: str) -> list[dict[str, Any]]:
        """Le incoerenze non riparabili ancora presenti: un avviso chiaro ciascuna."""
        return self._incoerenze("WHERE fascicolo_id=? AND stato=?", (fascicolo_id, AVVISO))

    def incoerenze(self, fascicolo_id: str = "", *, stato: str = "", limite: int = 500) -> list[dict[str, Any]]:
        condizioni, parametri = [], []
        if fascicolo_id:
            condizioni.append("fascicolo_id=?")
            parametri.append(fascicolo_id)
        if stato:
            condizioni.append("stato=?")
            parametri.append(stato)
        dove = ("WHERE " + " AND ".join(condizioni)) if condizioni else ""
        return self._incoerenze(f"{dove} ORDER BY ultima_vista DESC LIMIT {int(limite)}", tuple(parametri))

    def _incoerenze(self, coda: str, parametri: tuple) -> list[dict[str, Any]]:
        if not self.file.exists():
            return []
        with self._conn() as conn:
            righe = conn.execute(f"SELECT * FROM incoerenze {coda}", parametri).fetchall()
        return [{**dict(r), "dati": json.loads(r["dati"] or "{}")} for r in righe]

    def ultimo_giro(self, fascicolo_id: str) -> dict[str, Any] | None:
        if not self.file.exists():
            return None
        with self._conn() as conn:
            riga = conn.execute("SELECT * FROM giri WHERE fascicolo_id=? ORDER BY id DESC LIMIT 1", (fascicolo_id,)).fetchone()
        return dict(riga) if riga else None

    def giri(self, *, fascicolo_id: str = "", limite: int = 200) -> list[dict[str, Any]]:
        if not self.file.exists():
            return []
        with self._conn() as conn:
            if fascicolo_id:
                righe = conn.execute("SELECT * FROM giri WHERE fascicolo_id=? ORDER BY id DESC LIMIT ?", (fascicolo_id, limite))
            else:
                righe = conn.execute("SELECT * FROM giri ORDER BY id DESC LIMIT ?", (limite,))
            return [dict(r) for r in righe.fetchall()]

    def riepilogo(self) -> dict[str, dict[str, int]]:
        """Per codice di incoerenza: quante aperte, riparate, avvisi, chiuse."""
        if not self.file.exists():
            return {}
        with self._conn() as conn:
            righe = conn.execute("SELECT codice, stato, COUNT(*) n FROM incoerenze GROUP BY codice, stato").fetchall()
        risultato: dict[str, dict[str, int]] = {}
        for r in righe:
            risultato.setdefault(r["codice"], {})[r["stato"]] = int(r["n"])
        return risultato


__all__ = ["APERTA", "AVVISO", "CHIUSA", "NOME_FILE", "RIPARATA", "RegistroGuardiano", "TENTATIVI_MASSIMI", "percorso"]
