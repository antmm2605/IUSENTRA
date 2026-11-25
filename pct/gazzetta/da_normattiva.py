"""Testo degli atti normativi della Gazzetta dalla biblioteca Normattiva, senza riscaricarli dal sito.

Gli atti normativi della Serie generale (codice redazionale «AAG…», per esempio «26G00222») sono anche nella
biblioteca Normattiva articolo per articolo; l'edizione porta lo stesso codice redazionale nel nome del file
ufficiale («2026-11-09_26G00222_ORIGINALE_V0.xml»). Si collega l'atto solo se coincidono codice redazionale e
numero dell'atto (e, quando la Gazzetta lo indica, la data dell'atto): il testo salvato dichiara la fonte
(«Normattiva, testo originario» o «Normattiva, testo vigente al gg/mm/aaaa») e il collegamento ufficiale.
Si preferisce l'edizione originaria, che corrisponde al testo pubblicato in Gazzetta.

Gli atti collegati non si riscaricano più dal sito (``ArchivioGazzetta.atti_senza_testo`` salta gli atti con
testo): il recupero dal sito resta per gli atti «A» e per le serie speciali.

Lettura incrementale (verifica del 24/11/2026 sull'8080): rileggere a ogni giro orario tutta la tabella
``normative_documents`` (1,9 GB con il testo degli atti) richiedeva 35 minuti su disco lento. Le edizioni con codice
redazionale si copiano nell'archivio della Gazzetta (``normattiva_edizioni``) a lotti, per identificativo crescente e
con un tempo massimo; il cursore (``normattiva_cursore``) riparte da dove si era fermato. Se la biblioteca viene
sostituita (altro file, o identificativi più bassi del cursore) l'indice si ricostruisce da capo.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct.gazzetta.archivio import ArchivioGazzetta

CODICE_ATTO_NORMATIVO = re.compile(r"\d{2}G\d{5}")


TEMPO_MASSIMO = 300.0  # secondi per giro; il resto dell'indice al giro dopo
LOTTO = 2000

_SCHEMA_INDICE = (
    "CREATE TABLE IF NOT EXISTS normattiva_edizioni (id INTEGER PRIMARY KEY, codice TEXT NOT NULL, xml_entry TEXT, "
    "numero TEXT, data_atto TEXT, urn TEXT, redazione_id TEXT)",
    "CREATE INDEX IF NOT EXISTS normattiva_edizioni_codice ON normattiva_edizioni (codice)",
    "CREATE TABLE IF NOT EXISTS normattiva_cursore (chiave TEXT PRIMARY KEY, biblioteca TEXT NOT NULL, "
    "ultimo_id INTEGER NOT NULL, aggiornato_il TEXT NOT NULL)",
)


def _identita_biblioteca(percorso: Path) -> str:
    """Stesso file (percorso e inode): gli identificativi restano validi; un file nuovo riparte da capo."""
    stato = percorso.stat()
    return f"{percorso.resolve()}|{stato.st_ino}"


def aggiorna_indice(conn: sqlite3.Connection, gu: sqlite3.Connection, *, biblioteca: str, scadenza: float,
                    lotto: int = LOTTO, orologio=time.monotonic, quando: str = "") -> dict[str, Any]:
    """Copia nell'archivio della Gazzetta le edizioni nuove con codice redazionale, a lotti fino a ``scadenza``."""
    for istruzione in _SCHEMA_INDICE:
        gu.execute(istruzione)
    riga = gu.execute("SELECT biblioteca, ultimo_id FROM normattiva_cursore WHERE chiave='normattiva'").fetchone()
    massimo = conn.execute("SELECT COALESCE(MAX(id), 0) FROM normative_documents").fetchone()[0]
    ultimo = int(riga[1]) if riga and riga[0] == biblioteca else 0
    ricostruito = not riga or riga[0] != biblioteca or ultimo > massimo
    if ricostruito:
        gu.execute("DELETE FROM normattiva_edizioni")
        ultimo = 0
    nuove, completo = 0, False
    while True:
        if orologio() >= scadenza:
            break
        righe = conn.execute("SELECT id, xml_entry, numero, data_atto, urn, redazione_id FROM normative_documents "
                             "WHERE id > ? ORDER BY id LIMIT ?", (ultimo, lotto)).fetchall()
        if not righe:
            completo = True
            break
        for riga_doc in righe:
            trovato = re.search(r"_(\d{2}G\d{5})_", str(riga_doc[1] or ""))
            if trovato:
                gu.execute("INSERT OR REPLACE INTO normattiva_edizioni VALUES (?,?,?,?,?,?,?)",
                           (riga_doc[0], trovato.group(1), *riga_doc[1:]))
                nuove += 1
        ultimo = int(righe[-1][0])
        gu.execute("INSERT INTO normattiva_cursore VALUES ('normattiva', ?, ?, ?) ON CONFLICT(chiave) DO UPDATE SET "
                   "biblioteca=excluded.biblioteca, ultimo_id=excluded.ultimo_id, aggiornato_il=excluded.aggiornato_il",
                   (biblioteca, ultimo, quando))
        gu.commit()
    gu.commit()
    return {"edizioni_nuove": nuove, "indice_completo": completo, "indice_ricostruito": ricostruito}


def _edizioni_del_codice(gu: sqlite3.Connection, codice: str) -> list[tuple]:
    return [tuple(r) for r in gu.execute("SELECT id, xml_entry, numero, data_atto, urn, redazione_id "
                                         "FROM normattiva_edizioni WHERE codice=?", (codice,))]


def _scegli(edizioni: list[tuple]) -> tuple:
    originali = [e for e in edizioni if "ORIGINALE" in str(e[1])]
    candidati = originali or edizioni
    return sorted(candidati, key=lambda e: (str(e[5] or ""), e[0]))[-1]


def _testo(conn: sqlite3.Connection, documento: int) -> tuple[str, int]:
    righe = conn.execute("SELECT article_text FROM normative_articles WHERE document_id=? ORDER BY id", (documento,)).fetchall()
    blocchi = [str(r[0]).strip() for r in righe if r[0] and str(r[0]).strip()]
    return "\n\n".join(blocchi), len(blocchi)


def collega(archivio: ArchivioGazzetta, normattiva_db: str | Path, *, adesso: datetime | None = None,
            tempo_massimo: float = TEMPO_MASSIMO, lotto: int = LOTTO, orologio=time.monotonic) -> dict[str, Any]:
    """Salva il testo Normattiva per gli atti normativi della Gazzetta che non hanno ancora un testo."""
    quando = (adesso or datetime.now(timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    scadenza = orologio() + float(tempo_massimo)
    percorso = Path(normattiva_db)
    with closing(sqlite3.connect(f"file:{percorso}?mode=ro", uri=True, timeout=30)) as conn:
        with closing(sqlite3.connect(str(archivio.percorso), timeout=120)) as gu:
            indice = aggiorna_indice(conn, gu, biblioteca=_identita_biblioteca(percorso), scadenza=scadenza,
                                     lotto=lotto, orologio=orologio, quando=quando)
            atti = gu.execute(
                "SELECT a.id, a.codice_redazionale, a.numero_atto, a.data_atto, a.intestazione FROM atti a "
                "WHERE a.serie='SG' AND a.id NOT IN (SELECT id FROM testi)").fetchall()
            edizioni = {}
            for _atto_id, codice, *_resto in atti:
                if CODICE_ATTO_NORMATIVO.fullmatch(str(codice or "")) and codice not in edizioni:
                    edizioni[codice] = _edizioni_del_codice(gu, codice)
        esito = {"candidati": 0, "collegati": 0, "non_in_biblioteca": 0, "numero_discorde": 0, **indice,
                 "tempo_scaduto": False}
        for atto_id, codice, numero_atto, data_atto, intestazione in atti:
            if not CODICE_ATTO_NORMATIVO.fullmatch(str(codice or "")):
                continue
            if orologio() >= scadenza:
                esito["tempo_scaduto"] = True
                break
            esito["candidati"] += 1
            if not edizioni.get(codice):
                esito["non_in_biblioteca"] += 1
                continue
            edizione = _scegli(edizioni[codice])
            documento, xml_entry, numero, data, urn, redazione = edizione
            if (numero_atto and str(numero or "").lstrip("0") != str(numero_atto).lstrip("0")) or \
                    (data_atto and data and str(data)[:10] != str(data_atto)[:10]):
                esito["numero_discorde"] += 1
                continue
            testo, articoli = _testo(conn, documento)
            if not testo:
                esito["non_in_biblioteca"] += 1
                continue
            originale = "ORIGINALE" in str(xml_entry)
            fonte = ("Normattiva, testo originario" if originale
                     else f"Normattiva, testo vigente al {'/'.join(reversed(str(redazione)[:10].split('-')))}")
            archivio.salva_testo(atto_id, testo=testo, intestazione=str(intestazione or ""),
                                 sha256=hashlib.sha256(testo.encode("utf-8")).hexdigest(),
                                 url_testo=f"https://www.normattiva.it/uri-res/N2Ls?{urn}", articoli=articoli,
                                 letto_il=quando, fonte=f"{fonte} (codice redazionale {codice})")
            esito["collegati"] += 1
    if not indice["indice_completo"]:
        esito["tempo_scaduto"] = True
    return esito


__all__ = ["aggiorna_indice", "collega"]
