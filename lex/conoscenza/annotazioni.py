"""Annotazioni dell'avvocato sulle schede di istituto, nel SQL dello studio (SQLite o PostgreSQL).

Sono conoscenza dello studio, non comune: non entrano mai nei record generati e sopravvivono a ogni rigenerazione
perché sono legate all'ID stabile della scheda (e, se serve, alla chiave della voce: una norma o una pronuncia), non al
titolo né alla revisione. Ogni nota registra la revisione della scheda su cui è stata scritta: se la scheda è stata
rigenerata dopo, l'interfaccia lo dice. Append-only: una correzione è una nuova nota che sostituisce la precedente.
L'esito «favorevole/contrario» su una pronuncia è una valutazione dell'avvocato, non del software.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

TABELLA = "conoscenza_annotazioni"
SCHEMA = """CREATE TABLE IF NOT EXISTS conoscenza_annotazioni (
 id TEXT PRIMARY KEY, scheda_id TEXT NOT NULL, sezione TEXT NOT NULL, voce TEXT NOT NULL,
 revisione_scheda INTEGER NOT NULL, attore TEXT NOT NULL, creato_il TEXT NOT NULL, sostituisce TEXT NOT NULL,
 dati_json TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS idx_conoscenza_annotazioni_scheda ON conoscenza_annotazioni(scheda_id)"""
ESITI = ("", "favorevole", "contrario", "non pertinente", "da approfondire")
SEZIONI_AMMESSE = ("generale", "presupposti", "eccezioni", "termini", "rimedi", "giudice_rito", "prove_oneri",
                   "documenti", "questioni", "orientamenti", "fonti")


class Annotazioni:
    def __init__(self, studio_db):
        self.db = studio_db

    def _pg(self) -> bool:
        return getattr(self.db, "backend_kind", "") == "postgresql"

    def _esiste(self) -> bool:
        if self.db is None:
            return False
        if self._pg():
            return self.db.conn.execute(f"SELECT to_regclass('{TABELLA}')").fetchone()[0] is not None
        return self.db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABELLA,)).fetchone() is not None

    def _commit(self) -> None:
        (self.db.raw_conn if self._pg() else self.db.conn).commit()

    def elenco(self, scheda_id: str) -> list[dict[str, Any]]:
        """Note in vigore della scheda (quelle sostituite da una nota successiva restano nello storico)."""
        if not self._esiste():
            return []
        righe = self.db.conn.execute(f"SELECT dati_json FROM {TABELLA} WHERE scheda_id=? ORDER BY creato_il, id",
                                     (scheda_id,)).fetchall()
        tutte = [json.loads(r[0]) for r in righe]
        sostituite = {n["sostituisce"] for n in tutte if n.get("sostituisce")}
        return [n for n in tutte if n["id"] not in sostituite]

    def aggiungi(self, scheda_id: str, *, sezione: str, voce: str, testo: str, esito: str, attore: str,
                 revisione_scheda: int, sostituisce: str = "") -> dict[str, Any]:
        if self.db is None:
            raise RuntimeError("Archivio SQL dello studio non disponibile.")
        testo = " ".join(str(testo or "").split())[:4000]
        if not str(attore).strip():
            raise ValueError("Utente non riconosciuto.")
        if sezione not in SEZIONI_AMMESSE:
            raise ValueError("Sezione della scheda non valida.")
        if esito not in ESITI:
            raise ValueError("Valutazione non valida.")
        if not testo and not esito:
            raise ValueError("Scrivi la nota o scegli una valutazione.")
        for sql in SCHEMA.split(";"):
            if sql.strip():
                self.db.conn.execute(sql)
        self._commit()
        ora = datetime.now(timezone.utc).isoformat(timespec="seconds")
        ident = hashlib.sha256(json.dumps([scheda_id, sezione, voce, testo, esito, attore, ora, sostituisce]).encode()).hexdigest()[:24]
        nota = {"id": ident, "scheda_id": scheda_id, "sezione": sezione, "voce": str(voce or "")[:300], "testo": testo,
                "esito": esito, "attore": attore, "creato_il": ora, "revisione_scheda": int(revisione_scheda),
                "sostituisce": sostituisce}
        self.db.conn.execute(f"INSERT INTO {TABELLA} (id,scheda_id,sezione,voce,revisione_scheda,attore,creato_il,sostituisce,dati_json) "
                             "VALUES (?,?,?,?,?,?,?,?,?)", (ident, scheda_id, sezione, nota["voce"], nota["revisione_scheda"],
                                                         attore, ora, sostituisce, json.dumps(nota, ensure_ascii=False)))
        self._commit()
        return nota


def con_stato(note: list[dict[str, Any]], scheda: dict[str, Any]) -> list[dict[str, Any]]:
    """Ogni nota dice se la voce a cui si riferisce c'è ancora e se la scheda è cambiata dopo la nota."""
    chiavi = {f"{f['tipo']}:{f['chiave']}" for f in scheda.get("fonti", [])}
    testi = {v["testo"] for s in scheda.get("sezioni", {}).values() for v in s["voci"]}
    out = []
    for n in note:
        voce_presente = (not n["voce"]) or n["voce"] in chiavi or n["voce"] in testi
        out.append({**n, "voce_presente": voce_presente,
                    "scheda_cambiata_dopo": int(scheda.get("revisione", 0)) > int(n.get("revisione_scheda", 0))})
    return out
