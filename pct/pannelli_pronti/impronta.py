"""L'impronta delle fonti di un fascicolo: un solo controllore per tutti i pannelli.

L'impronta cambia se cambia anche una sola delle fonti da cui i pannelli del fascicolo sono calcolati:

- i contatori di revisione del fascicolo in ``studio.db`` e nel registro delle letture (trigger SQL su ogni tabella
  con la colonna del fascicolo: riga del fascicolo con documenti, attività e scadenze incorporati, scadenze,
  appuntamenti, parcelle, catalogo dei documenti, depositi, CTU, mediazioni, fatti e oggetti letti, verifiche...);
- i contatori delle tabelle senza fascicolo lette dai pannelli (anagrafiche, configurazione, posta);
- dimensione e data di modifica dei file dello studio letti dai pannelli fuori da ``studio.db``;
- la generazione del fascicolo, incrementata da ogni richiesta di scrittura sul fascicolo;
- il giorno corrente a Roma (i termini dipendono dal giorno) e la versione dell'applicazione.

Sono poche query per chiave primaria e qualche ``stat``: pochi millisecondi. Se la preparazione dei trigger manca
in uno dei due database, l'impronta è ``None`` e chi la usa non deve servire payload salvati.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from pct.pannelli_pronti import revisioni

ROMA = ZoneInfo("Europe/Rome")


@dataclass(frozen=True)
class FontiTenant:
    """I percorsi delle fonti di uno studio."""

    studio_db: str
    registro_db: str
    file: tuple[str, ...] = field(default_factory=tuple)
    pec_db: str = ""


def giorno_roma(adesso: datetime | None = None) -> str:
    momento = adesso or datetime.now(ROMA)
    return (momento if momento.tzinfo else momento.replace(tzinfo=ROMA)).astimezone(ROMA).date().isoformat()


def _connessione_lettura(percorso: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA query_only=1")
    return conn


def revisioni_database(percorso: str, fascicolo_id: str) -> tuple[str, int, tuple[tuple[str, int], ...]] | None:
    if not percorso or not os.path.exists(percorso):
        return None
    conn = _connessione_lettura(percorso)
    try:
        firma, revisione, tabelle = revisioni.leggi(conn, fascicolo_id)
    finally:
        conn.close()
    return (firma, revisione, tabelle) if firma else None


def stato_file(percorso: str) -> tuple[str, int, int, int, int]:
    """(percorso, mtime_ns, dimensione) del file e, per i database SQLite in WAL, anche del file -wal."""
    risultato = []
    for nome in (percorso, percorso + "-wal"):
        try:
            info = os.stat(nome)
            # SQLite può creare o troncare un WAL vuoto anche in apertura. Nessun frame significa
            # che il suo stato non cambia i dati leggibili dal pannello.
            if nome != percorso and info.st_size == 0:
                risultato.append((0, -1))
            else:
                risultato.append((info.st_mtime_ns, info.st_size))
        except OSError:
            risultato.append((0, -1))
    return (percorso, *risultato[0], *risultato[1])


def componenti(fonti: FontiTenant, fascicolo_id: str, *, generazione: int, versione: str,
               adesso: datetime | None = None) -> dict | None:
    """Le parti dell'impronta, leggibili (servono alla diagnosi e ai test)."""
    studio = revisioni_database(fonti.studio_db, fascicolo_id)
    registro = revisioni_database(fonti.registro_db, fascicolo_id)
    if studio is None or registro is None:
        return None
    parti = {
        "versione": str(versione),
        "giorno": giorno_roma(adesso),
        "generazione": int(generazione),
        "studio": [studio[0], studio[1], list(studio[2])],
        "registro": [registro[0], registro[1], list(registro[2])],
        "file": [list(stato_file(p)) for p in sorted(set(fonti.file))],
    }
    if fonti.pec_db:
        pec = revisioni_database(fonti.pec_db, fascicolo_id)
        if pec is None:
            # Compatibilità con un archivio che deve ancora ricevere i trigger.
            parti["file"].append(list(stato_file(fonti.pec_db)))
            parti["file"].sort()
        else:
            parti["pec"] = [pec[0], pec[1], list(pec[2])]
    return parti


def impronta_componenti(parti: dict | None, *, dipende_dal_giorno: bool = True) -> str | None:
    if parti is None:
        return None
    if not dipende_dal_giorno:
        parti = {nome: valore for nome, valore in parti.items() if nome != "giorno"}
    grezzo = json.dumps(parti, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()


def impronta(fonti: FontiTenant, fascicolo_id: str, *, generazione: int, versione: str,
             adesso: datetime | None = None, dipende_dal_giorno: bool = True) -> str | None:
    parti = componenti(fonti, fascicolo_id, generazione=generazione, versione=versione, adesso=adesso)
    return impronta_componenti(parti, dipende_dal_giorno=dipende_dal_giorno)
