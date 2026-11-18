"""L'ordine in cui il calcolo in sfondo prepara i pannelli di tutti i fascicoli non archiviati.

1. fascicoli aperti di recente (l'avvocato ci sta lavorando);
2. fascicoli con un termine aperto o un'udienza futura, dal più vicino;
3. tutti gli altri non archiviati, dal modificato più di recente.

Legge solo righe già registrate (fascicoli, scadenze dello studio, sintesi del registro delle letture) in sola
lettura: nessun motore, nessun documento. Se una tabella manca la sua parte dell'ordine si salta.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from pct.pannelli_pronti.impronta import ROMA, FontiTenant

logger = logging.getLogger(__name__)
STATI_ESCLUSI = frozenset({"ARCHIVIATO", "ARCHIVIATA", "ELIMINATO"})
STATI_SCADENZA_APERTI = ("APERTO", "BOZZA", "SCADUTO")


def _righe(percorso: str, sql: str, parametri: tuple = ()) -> list[tuple]:
    if not percorso:
        return []
    try:
        conn = sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=5)
    except sqlite3.Error:
        return []
    try:
        conn.execute("PRAGMA query_only=1")
        return list(conn.execute(sql, parametri).fetchall())
    except sqlite3.Error as exc:
        logger.debug("Ordine dei pannelli: %s non leggibile (%s)", percorso, exc)
        return []
    finally:
        conn.close()


def fascicoli_per_priorita(fonti: FontiTenant, aperti_di_recente: list[str], *,
                           adesso: datetime | None = None) -> list[str]:
    """Gli id dei fascicoli non archiviati nell'ordine di preparazione."""
    oggi = (adesso or datetime.now(ROMA)).astimezone(ROMA).date().isoformat()
    colonne = {str(r[1]) for r in _righe(fonti.studio_db, "PRAGMA table_info('fascicoli')")}
    stato = "UPPER(COALESCE(stato,''))" if "stato" in colonne else "''"
    modificato = "COALESCE(modificato_il,'')" if "modificato_il" in colonne else "''"
    fascicoli = _righe(fonti.studio_db, f"SELECT id, {stato}, {modificato} FROM fascicoli") if "id" in colonne else []
    if not fascicoli:
        # Studio senza la tabella SQL dei fascicoli: si usa la sintesi del registro delle letture.
        fascicoli = _righe(fonti.registro_db, "SELECT fascicolo_id, UPPER(COALESCE(stato,'')), COALESCE(aggiornato_il,'') "
                                              "FROM letture_sintesi_fascicolo")
    attivi = {str(fid): modificato for fid, stato, modificato in fascicoli
              if fid and str(stato).strip() not in STATI_ESCLUSI}
    if not attivi:
        return []
    termini: dict[str, str] = {}
    segnaposti = ",".join("?" for _ in STATI_SCADENZA_APERTI)
    for fid, data in _righe(fonti.studio_db,
                            f"SELECT id_fascicolo, MIN(substr(data_scadenza,1,10)) FROM scadenze WHERE stato IN ({segnaposti}) "
                            "AND COALESCE(id_fascicolo,'')<>'' AND substr(data_scadenza,1,10)>=? GROUP BY id_fascicolo",
                            (*STATI_SCADENZA_APERTI, oggi)):
        termini[str(fid)] = str(data)
    for fid, data in _righe(fonti.registro_db,
                            "SELECT fascicolo_id, MIN(substr(prossima_udienza,1,10)) FROM letture_sintesi_fascicolo "
                            "WHERE COALESCE(prossima_udienza,'')<>'' AND substr(prossima_udienza,1,10)>=? GROUP BY fascicolo_id",
                            (oggi,)):
        fid = str(fid)
        if fid not in termini or str(data) < termini[fid]:
            termini[fid] = str(data)
    recenti = [f for f in dict.fromkeys(map(str, aperti_di_recente)) if f in attivi]
    vicini = sorted((f for f in termini if f in attivi and f not in recenti), key=lambda f: (termini[f], f))
    gia = set(recenti) | set(vicini)
    altri = sorted((f for f in attivi if f not in gia), key=lambda f: (attivi[f], f), reverse=True)
    return [*recenti, *vicini, *altri]
