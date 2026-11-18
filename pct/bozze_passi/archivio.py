"""Il registro delle bozze dei passi di uno studio (SQLite accanto agli altri archivi «intelligence» del tenant).

Per ogni fascicolo e bozza conserva il documento creato nel fascicolo, l'impronta del testo generato e
l'impronta del contenuto salvato, così il lavoro in sfondo sa se l'avvocato l'ha modificata (allora la sua
versione resta e si segnala solo che i dati sono cambiati) e la pagina legge lo stato senza calcolare nulla.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

NOME_FILE = "bozze_passi.sqlite"
ROME_TZ = ZoneInfo("Europe/Rome")

STATO_PRONTA = "pronta"  # testo del software, non toccato
STATO_MODIFICATA = "modificata"  # salvata dall'avvocato
STATO_DATI_CAMBIATI = "dati_cambiati"  # modificata dall'avvocato e poi cambiate le fonti: la sua versione resta
STATO_SUPERATA = "superata"  # il passo non c'è più

_SCHEMA = """
CREATE TABLE IF NOT EXISTS bozze_passi (
    fascicolo_id TEXT NOT NULL,
    chiave TEXT NOT NULL,
    documento_id TEXT NOT NULL,
    tipo TEXT NOT NULL,
    titolo TEXT NOT NULL,
    modello TEXT NOT NULL,
    modello_titolo TEXT NOT NULL,
    norma TEXT NOT NULL DEFAULT '',
    da_completare TEXT NOT NULL DEFAULT '[]',
    passi TEXT NOT NULL DEFAULT '[]',
    impronta_testo TEXT NOT NULL,
    impronta_contenuto TEXT NOT NULL,
    impronta_fonti_attuali TEXT NOT NULL DEFAULT '',
    stato TEXT NOT NULL,
    creata_il TEXT NOT NULL,
    aggiornata_il TEXT NOT NULL,
    dati_cambiati_il TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (fascicolo_id, chiave)
);
"""


def adesso() -> str:
    return datetime.now(ROME_TZ).replace(microsecond=0).isoformat()


@dataclass
class VoceBozza:
    fascicolo_id: str
    chiave: str
    documento_id: str
    tipo: str
    titolo: str
    modello: str
    modello_titolo: str
    norma: str = ""
    da_completare: list[str] = field(default_factory=list)
    passi: list[dict[str, str]] = field(default_factory=list)
    impronta_testo: str = ""  # del testo che il software ha generato l'ultima volta
    impronta_contenuto: str = ""  # sha256 del contenuto salvato dal software nel documento
    impronta_fonti_attuali: str = ""  # del testo che il software genererebbe oggi (diversa se i dati sono cambiati)
    stato: str = STATO_PRONTA
    creata_il: str = ""
    aggiornata_il: str = ""
    dati_cambiati_il: str = ""


class ArchivioBozze:
    def __init__(self, percorso: str | Path) -> None:
        self.percorso = Path(percorso)

    def _conn(self) -> sqlite3.Connection:
        self.percorso.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.percorso, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.executescript(_SCHEMA)
        return conn

    @staticmethod
    def _voce(riga: sqlite3.Row) -> VoceBozza:
        dati = dict(riga)
        dati["da_completare"] = json.loads(dati["da_completare"] or "[]")
        dati["passi"] = json.loads(dati["passi"] or "[]")
        return VoceBozza(**dati)

    def del_fascicolo(self, fascicolo_id: str) -> list[VoceBozza]:
        if not self.percorso.exists():
            return []
        with closing(self._conn()) as conn:
            righe = conn.execute("SELECT * FROM bozze_passi WHERE fascicolo_id = ? ORDER BY creata_il, chiave",
                                 (fascicolo_id,)).fetchall()
        return [self._voce(r) for r in righe]

    def salva(self, voce: VoceBozza) -> None:
        dati = asdict(voce)
        dati["da_completare"] = json.dumps(voce.da_completare, ensure_ascii=False)
        dati["passi"] = json.dumps(voce.passi, ensure_ascii=False)
        colonne = list(dati)
        with closing(self._conn()) as conn, conn:
            conn.execute(
                f"INSERT INTO bozze_passi ({', '.join(colonne)}) VALUES ({', '.join('?' for _ in colonne)}) "
                f"ON CONFLICT(fascicolo_id, chiave) DO UPDATE SET "
                + ", ".join(f"{c} = excluded.{c}" for c in colonne if c not in {"fascicolo_id", "chiave"}),
                [dati[c] for c in colonne],
            )

    def elimina(self, fascicolo_id: str, chiave: str) -> None:
        if not self.percorso.exists():
            return
        with closing(self._conn()) as conn, conn:
            conn.execute("DELETE FROM bozze_passi WHERE fascicolo_id = ? AND chiave = ?", (fascicolo_id, chiave))


def percorso_archivio(data_paths: dict[str, Any]) -> Path | None:
    studio_db = str((data_paths or {}).get("STUDIO_DB") or "")
    return Path(studio_db).parent / "intelligence" / NOME_FILE if studio_db else None


__all__ = ["STATO_DATI_CAMBIATI", "STATO_MODIFICATA", "STATO_PRONTA", "STATO_SUPERATA", "ArchivioBozze", "VoceBozza",
           "adesso", "percorso_archivio"]
