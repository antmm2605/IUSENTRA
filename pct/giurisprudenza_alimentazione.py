"""Alimentazione continua dell'archivio di giurisprudenza (decisione dell'avvocato del 06/11/2026: in locale, 24 ore su 24).

Un giro, sotto lo stesso blocco dell'acquisizione SentenzeWeb (``acquisizione.lock``), fa nell'ordine:
1. acquisizione incrementale e recupero dei testi in oscuramento da SentenzeWeb (``pct/sentenzeweb_nightly.py``),
   con un numero di recuperi per giro configurabile;
2. riparazione dei collegamenti salvati da una versione precedente dell'importatore come pagina di elenco invece che
   come pagina della decisione;
3. lettura delle citazioni (norme applicate e precedenti richiamati) delle decisioni non ancora lette con la versione
   corrente del lettore (``pct/giurisprudenza_citazioni.py``), nell'archivio SentenzeWeb e negli archivi degli studi
   (Corte costituzionale).
Si attiva solo con ``IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA=continua``: online l'acquisizione resta spenta.
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from pct.giurisprudenza_citazioni import VERSIONE_LETTORE, norme_citate, precedenti_citati

URL_SENTENZEWEB = "https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select"
_TABELLA_LETTURE = """CREATE TABLE IF NOT EXISTS citazioni_letture (
    sentenza_id INTEGER PRIMARY KEY REFERENCES sentenze(id) ON DELETE CASCADE,
    versione TEXT NOT NULL, letto_utc TEXT NOT NULL, norme INTEGER NOT NULL, precedenti INTEGER NOT NULL)"""


def attiva(config: dict[str, Any] | None = None) -> bool:
    valore = (config or {}).get("IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA") or os.getenv("IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA") or ""
    return str(valore).strip().lower() == "continua"


def collegamento_decisione(identificativo: str) -> str:
    """Il collegamento ufficiale alla singola decisione, come lo costruisce l'importatore attuale."""
    return URL_SENTENZEWEB + "?" + urlencode({"q": "id:" + identificativo, "rows": 1, "wt": "json"})


def ripara_collegamenti(connessione: sqlite3.Connection) -> int:
    """Decisioni con l'indirizzo di una pagina di elenco («cursorMark») al posto del collegamento alla decisione."""
    righe = connessione.execute("SELECT id, uuid_interno FROM sentenze WHERE url_pagina_ufficiale LIKE '%cursorMark%' "
                                "AND uuid_interno LIKE 'sentenzeweb:sn%'").fetchall()
    for id_, uuid in righe:
        connessione.execute("UPDATE sentenze SET url_pagina_ufficiale=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                            (collegamento_decisione(uuid.split(":", 1)[1]), id_))
    return len(righe)


def leggi_citazioni(owner: Any, *, limite: int = 20000, scadenza: float | None = None) -> dict[str, int]:
    """Legge le citazioni delle decisioni con testo non ancora lette dalla versione corrente; incrementale e ripetibile."""
    lette = norme = precedenti = 0
    with closing(owner._connect()) as connessione:
        connessione.execute(_TABELLA_LETTURE)
        righe = connessione.execute(
            "SELECT s.id, s.testo_integrale, s.anno_sentenza FROM sentenze s LEFT JOIN citazioni_letture c ON c.sentenza_id=s.id "
            "WHERE s.testo_integrale_presente=1 AND (c.sentenza_id IS NULL OR c.versione<>?) ORDER BY s.id LIMIT ?",
            (VERSIONE_LETTORE, max(1, int(limite)))).fetchall()
        adesso = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for blocco_inizio in range(0, len(righe), 500):
            with connessione:
                for id_, testo, anno in righe[blocco_inizio:blocco_inizio + 500]:
                    trovate = norme_citate(testo)
                    richiamati = precedenti_citati(testo, anno_decisione=anno)
                    owner._replace_norme(connessione, id_, trovate)
                    owner._replace_precedenti(connessione, id_, richiamati)
                    connessione.execute("INSERT OR REPLACE INTO citazioni_letture VALUES (?,?,?,?,?)",
                                        (id_, VERSIONE_LETTORE, adesso, len(trovate), len(richiamati)))
                    lette, norme, precedenti = lette + 1, norme + len(trovate), precedenti + len(richiamati)
            if scadenza and time.monotonic() > scadenza:
                break
        restanti = connessione.execute(
            "SELECT COUNT(*) FROM sentenze s LEFT JOIN citazioni_letture c ON c.sentenza_id=s.id "
            "WHERE s.testo_integrale_presente=1 AND (c.sentenza_id IS NULL OR c.versione<>?)", (VERSIONE_LETTORE,)).fetchone()[0]
    return {"lette": lette, "norme": norme, "precedenti": precedenti, "da_leggere": int(restanti)}


def esegui_giro(config: dict[str, Any], *, archivi_studi: list[str] | None = None, durata_massima_s: int = 3000) -> dict[str, Any]:
    if not attiva(config):
        return {"ok": True, "status": "spenta", "motivo": "alimentazione continua non abilitata (solo in locale)"}
    from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
    from pct.sentenzeweb_nightly import run_nightly
    from tools.sentenzeweb_importa import FileLock

    scadenza = time.monotonic() + durata_massima_s
    esito: dict[str, Any] = {"ok": True, "status": "completato"}
    esito["sentenzeweb"] = run_nightly(config)
    cartella = str(config.get("IUSENTRA_SENTENZEWEB_DIRECTORY") or os.getenv("IUSENTRA_SENTENZEWEB_DIRECTORY") or "").strip()
    if cartella and (Path(cartella) / "giurisprudenza_corpus.db").is_file():
        radice = Path(cartella).resolve()
        try:
            with FileLock(str(radice / "acquisizione.lock")):
                owner = GestioneCorpusGiurisprudenza(str(radice / "giurisprudenza_corpus.db"))
                with closing(owner._connect()) as connessione, connessione:
                    esito["collegamenti_riparati"] = ripara_collegamenti(connessione)
                esito["citazioni_cassazione"] = leggi_citazioni(owner, scadenza=scadenza)
        except BlockingIOError:
            esito["citazioni_cassazione"] = {"status": "acquisizione_in_corso"}
    for percorso in archivi_studi or []:
        if Path(percorso).is_file() and time.monotonic() < scadenza:
            esito.setdefault("citazioni_studi", {})[percorso] = leggi_citazioni(GestioneCorpusGiurisprudenza(percorso), scadenza=scadenza)
    return esito
