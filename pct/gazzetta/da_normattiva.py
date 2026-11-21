"""Testo degli atti normativi della Gazzetta dalla biblioteca Normattiva, senza riscaricarli dal sito.

Gli atti normativi della Serie generale (codice redazionale «AAG…», per esempio «26G00222») sono anche nella
biblioteca Normattiva articolo per articolo; l'edizione porta lo stesso codice redazionale nel nome del file
ufficiale («2026-11-09_26G00222_ORIGINALE_V0.xml»). Si collega l'atto solo se coincidono codice redazionale e
numero dell'atto (e, quando la Gazzetta lo indica, la data dell'atto): il testo salvato dichiara la fonte
(«Normattiva, testo originario» o «Normattiva, testo vigente al gg/mm/aaaa») e il collegamento ufficiale.
Si preferisce l'edizione originaria, che corrisponde al testo pubblicato in Gazzetta.

Gli atti collegati non si riscaricano più dal sito (``ArchivioGazzetta.atti_senza_testo`` salta gli atti con
testo): il recupero dal sito resta per gli atti «A» e per le serie speciali.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct.gazzetta.archivio import ArchivioGazzetta

CODICE_ATTO_NORMATIVO = re.compile(r"\d{2}G\d{5}")


def _edizioni(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    """codice redazionale → edizioni (id, xml_entry, numero, data_atto, urn, redazione_id)."""
    edizioni: dict[str, list[tuple]] = {}
    for riga in conn.execute("SELECT id, xml_entry, numero, data_atto, urn, redazione_id FROM normative_documents"):
        trovato = re.search(r"_(\d{2}G\d{5})_", str(riga[1] or ""))
        if trovato:
            edizioni.setdefault(trovato.group(1), []).append(tuple(riga))
    return edizioni


def _scegli(edizioni: list[tuple]) -> tuple:
    originali = [e for e in edizioni if "ORIGINALE" in str(e[1])]
    candidati = originali or edizioni
    return sorted(candidati, key=lambda e: (str(e[5] or ""), e[0]))[-1]


def _testo(conn: sqlite3.Connection, documento: int) -> tuple[str, int]:
    righe = conn.execute("SELECT article_text FROM normative_articles WHERE document_id=? ORDER BY id", (documento,)).fetchall()
    blocchi = [str(r[0]).strip() for r in righe if r[0] and str(r[0]).strip()]
    return "\n\n".join(blocchi), len(blocchi)


def collega(archivio: ArchivioGazzetta, normattiva_db: str | Path, *, adesso: datetime | None = None) -> dict[str, Any]:
    """Salva il testo Normattiva per gli atti normativi della Gazzetta che non hanno ancora un testo."""
    quando = (adesso or datetime.now(timezone.utc)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with closing(sqlite3.connect(f"file:{Path(normattiva_db)}?mode=ro", uri=True, timeout=30)) as conn:
        edizioni = _edizioni(conn)
        with closing(sqlite3.connect(f"file:{archivio.percorso}?mode=ro", uri=True, timeout=30)) as gu:
            atti = gu.execute(
                "SELECT a.id, a.codice_redazionale, a.numero_atto, a.data_atto, a.intestazione FROM atti a "
                "WHERE a.serie='SG' AND a.id NOT IN (SELECT id FROM testi)").fetchall()
        esito = {"candidati": 0, "collegati": 0, "non_in_biblioteca": 0, "numero_discorde": 0}
        for atto_id, codice, numero_atto, data_atto, intestazione in atti:
            if not CODICE_ATTO_NORMATIVO.fullmatch(str(codice or "")):
                continue
            esito["candidati"] += 1
            if codice not in edizioni:
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
    return esito


__all__ = ["collega"]
