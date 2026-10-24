"""Decisioni dello studio nel backend SQL nativo, SQLite o PostgreSQL."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

TABELLA = "schede_fonti_decisioni"
SCHEMA = """CREATE TABLE IF NOT EXISTS schede_fonti_decisioni (
 id TEXT PRIMARY KEY, tipo TEXT NOT NULL, riferimento TEXT NOT NULL,
 impronta TEXT NOT NULL, attore TEXT NOT NULL, creato_il TEXT NOT NULL,
 dati_json TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS idx_schede_fonti_tipo ON schede_fonti_decisioni(tipo);"""


def impronta(dati) -> str:
    return hashlib.sha256(json.dumps(dati, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def chiave(tipo, riferimento, digest):
    return impronta([tipo, riferimento, digest])


class DecisioniStudio:
    def __init__(self, studio_db):
        self.db = studio_db

    def _esiste(self):
        if self.db is None:
            return False
        if getattr(self.db, "backend_kind", "") == "postgresql":
            return self.db.conn.execute("SELECT to_regclass('schede_fonti_decisioni')").fetchone()[0] is not None
        return self.db.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABELLA,)).fetchone() is not None

    def leggi(self, tipo):
        # Una GET non crea tabelle né importa dati da archivi condivisi.
        if not self._esiste():
            return {}
        rows = self.db.conn.execute("SELECT id, dati_json FROM schede_fonti_decisioni WHERE tipo=?", (tipo,)).fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    def registra(self, tipo, eventi, attore):
        if self.db is None:
            raise RuntimeError("Archivio SQL dello studio non disponibile.")
        if not str(attore).strip():
            raise ValueError("Utente che approva non disponibile.")
        for sql in SCHEMA.split(";"):
            if sql.strip():
                self.db.conn.execute(sql)
        if getattr(self.db, "backend_kind", "") == "postgresql":
            self.db.raw_conn.commit()
        else:
            self.db.conn.commit()
        ora = datetime.now(timezone.utc).isoformat()
        rows = []
        for riferimento, digest, dati in eventi:
            record = dict(dati, attore=attore, creato_il=ora, riferimento=riferimento, impronta=digest)
            rows.append((chiave(tipo, riferimento, digest), riferimento, digest, record))
        def inserisci(conn, row):
            ident, rif, digest, dati = row
            precedente = conn.execute("SELECT dati_json FROM schede_fonti_decisioni WHERE id=?", (ident,)).fetchone()
            if precedente:
                vecchio = json.loads(precedente[0])
                if tipo == "proposta" and any(vecchio.get(k, "") != dati.get(k, "") for k in ("esito", "nota")):
                    raise ValueError("La proposta è già stata decisa: ricarica l'elenco.")
                return
            conn.execute("INSERT INTO schede_fonti_decisioni (id,tipo,riferimento,impronta,attore,creato_il,dati_json) "
                         "VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING",
                         (ident, tipo, rif, digest, attore, ora, json.dumps(dati, ensure_ascii=False)))
            if tipo == "proposta":
                salvata = json.loads(conn.execute("SELECT dati_json FROM schede_fonti_decisioni WHERE id=?", (ident,)).fetchone()[0])
                if any(salvata.get(k, "") != dati.get(k, "") for k in ("esito", "nota")):
                    raise ValueError("La proposta è già stata decisa: ricarica l'elenco.")
        self.db.salva_tabella(TABELLA, rows, inserisci, delete_all=False)
