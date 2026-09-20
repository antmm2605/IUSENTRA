"""Conta e toglie la copia in eccesso dentro `dati_json` dei fascicoli.

Fino alla 2.327.1 ogni fascicolo veniva salvato due volte: `dati_json`
conteneva il fascicolo intero — documenti, attivita' e depositi compresi — e
le stesse tre collezioni stavano anche nelle loro colonne. Dalla 2.328.0 la
colonna e' la fonte e `dati_json` non le duplica piu', ma le righe scritte
prima continuano a pesare il doppio finche' non vengono riscritte.

La logica sta qui, non nello script: la usano sia la riga di comando sia la
rotta di manutenzione, e devono fare esattamente la stessa cosa.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Le collezioni che hanno una colonna propria e non vanno duplicate.
COLLEZIONI_DUPLICATE = ("documenti", "attivita", "depositi_pct")


@dataclass
class EsitoArchivio:
    """Quanto pesa la copia in eccesso in un singolo studio."""

    studio: str
    percorso: str
    fascicoli: int = 0
    da_sgrassare: int = 0
    byte_in_eccesso: int = 0
    riscritte: int = 0
    errore: str = ""

    def come_dizionario(self) -> dict[str, Any]:
        return {
            "studio": self.studio,
            "fascicoli": self.fascicoli,
            "da_sgrassare": self.da_sgrassare,
            "mb_in_eccesso": round(self.byte_in_eccesso / 1048576, 2),
            "riscritte": self.riscritte,
            "errore": self.errore,
        }


def archivi_degli_studi(data_root: Path) -> list[Path]:
    """Gli `studio.db` di tutti gli studi sotto la radice dati."""
    radice = Path(data_root) / "tenants"
    if not radice.exists():
        locale = Path(data_root) / "studio.db"
        return [locale] if locale.exists() else []
    trovati = []
    for cartella in sorted(p for p in radice.iterdir() if p.is_dir()):
        db = cartella / "studio.db"
        if db.exists():
            trovati.append(db)
    return trovati


def _snellisci(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in COLLEZIONI_DUPLICATE}


def conta_eccesso(db: Path) -> EsitoArchivio:
    """Quanto spazio occupa la copia doppia. Non modifica nulla."""
    esito = EsitoArchivio(studio=Path(db).parent.name, percorso=str(db))
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            for riga in conn.execute("SELECT id, dati_json FROM fascicoli"):
                esito.fascicoli += 1
                grezzo = riga["dati_json"] or ""
                if not grezzo:
                    continue
                try:
                    payload = json.loads(grezzo)
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                if not any(k in payload for k in COLLEZIONI_DUPLICATE):
                    continue
                esito.da_sgrassare += 1
                esito.byte_in_eccesso += len(grezzo) - len(
                    json.dumps(_snellisci(payload), ensure_ascii=False)
                )
    except Exception as exc:
        esito.errore = str(exc)
    return esito


def sgrassa(db: Path) -> EsitoArchivio:
    """Riscrive solo `dati_json`. Le colonne fonte non vengono toccate mai."""
    esito = conta_eccesso(db)
    if esito.errore or not esito.da_sgrassare:
        return esito
    try:
        with sqlite3.connect(str(db), timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            for riga in list(conn.execute("SELECT id, dati_json FROM fascicoli")):
                grezzo = riga["dati_json"] or ""
                if not grezzo:
                    continue
                try:
                    payload = json.loads(grezzo)
                except Exception:
                    continue
                if not isinstance(payload, dict):
                    continue
                snello = _snellisci(payload)
                if len(snello) == len(payload):
                    continue
                conn.execute(
                    "UPDATE fascicoli SET dati_json = ? WHERE id = ?",
                    (json.dumps(snello, ensure_ascii=False), riga["id"]),
                )
                esito.riscritte += 1
            conn.commit()
    except Exception as exc:
        esito.errore = str(exc)
    return esito


def esamina_tutti(data_root: Path, *, riscrivi: bool = False) -> dict[str, Any]:
    archivi = archivi_degli_studi(Path(data_root))
    if not archivi:
        return {
            "ok": False,
            "messaggio": f"Nessuno studio.db trovato sotto {data_root}.",
            "studi": [],
        }
    esiti = [(sgrassa(db) if riscrivi else conta_eccesso(db)) for db in archivi]
    totale = sum(e.byte_in_eccesso for e in esiti)
    riscritte = sum(e.riscritte for e in esiti)
    errori = [e.errore for e in esiti if e.errore]
    return {
        "ok": not errori,
        "riscrittura_eseguita": bool(riscrivi),
        "mb_in_eccesso": round(totale / 1048576, 2),
        "righe_riscritte": riscritte,
        "errori": errori,
        "studi": [e.come_dizionario() for e in esiti],
        "messaggio": (
            f"Riscritte {riscritte} righe; {round(totale/1048576, 2)} MB di copia in eccesso trovati."
            if riscrivi
            else f"{round(totale/1048576, 2)} MB di copia in eccesso. Nessuna modifica eseguita."
        ),
    }
