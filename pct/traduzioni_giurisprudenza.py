"""Ricevute SQL delle traduzioni derivate: gli originali restano nel corpus."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_traduzioni (
 id TEXT PRIMARY KEY, sentenza_id INTEGER NOT NULL REFERENCES sentenze(id),
 source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64), source_language TEXT NOT NULL,
 target_language TEXT NOT NULL CHECK(target_language='it'), modello TEXT NOT NULL,
 revisione TEXT NOT NULL, sha256_modello TEXT NOT NULL, motore TEXT NOT NULL,
 stato TEXT NOT NULL CHECK(stato IN ('in_attesa','in_corso','completa','errore')),
 totale INTEGER NOT NULL CHECK(totale>0), errore TEXT NOT NULL DEFAULT '',
 creata_il TEXT NOT NULL, aggiornata_il TEXT NOT NULL,
 UNIQUE(sentenza_id,source_sha256,source_language,target_language)
);
CREATE TABLE IF NOT EXISTS corpus_traduzioni_segmenti (
 traduzione_id TEXT NOT NULL REFERENCES corpus_traduzioni(id), numero INTEGER NOT NULL,
 inizio INTEGER NOT NULL, fine INTEGER NOT NULL CHECK(fine>inizio), source_sha256 TEXT NOT NULL,
 stato TEXT NOT NULL CHECK(stato IN ('in_attesa','in_corso','completo')),
 testo_tradotto TEXT NOT NULL DEFAULT '', output_sha256 TEXT NOT NULL DEFAULT '',
 avviso TEXT NOT NULL DEFAULT '', claim_token TEXT NOT NULL DEFAULT '', aggiornata_il TEXT NOT NULL,
 PRIMARY KEY(traduzione_id,numero)
);
CREATE TABLE IF NOT EXISTS corpus_traduzioni_eventi (
 id INTEGER PRIMARY KEY, traduzione_id TEXT NOT NULL REFERENCES corpus_traduzioni(id),
 codice TEXT NOT NULL, creato_il TEXT NOT NULL
);
"""


class TraduzioniCorpus:
    def __init__(self, database):
        self.path = Path(database).resolve(strict=True)

    @contextmanager
    def connect(self, *, write=False):
        connection = sqlite3.connect(self.path.as_uri()+("?mode=rw" if write else "?mode=ro"),uri=True,timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        if not write:
            connection.execute("PRAGMA query_only=ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def ensure_schema(self):
        with self.connect(write=True) as connection:
            connection.executescript(SCHEMA)

    def existing(self, sid, source_sha, language):
        with self.connect() as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='corpus_traduzioni'").fetchone():
                return None
            row=connection.execute("SELECT * FROM corpus_traduzioni WHERE sentenza_id=? AND source_sha256=? AND source_language=? AND target_language='it'",(sid,source_sha,language)).fetchone()
            return dict(row) if row else None

    def begin(self, sid, source_sha, language, prepared, *, retry=False):
        self.ensure_schema()
        with self.connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row=connection.execute("SELECT * FROM corpus_traduzioni WHERE sentenza_id=? AND source_sha256=? AND source_language=? AND target_language='it'",(sid,source_sha,language)).fetchone()
            if row:
                if row['stato']=='errore' and retry:
                    connection.execute("UPDATE corpus_traduzioni_segmenti SET stato='in_attesa',claim_token='',aggiornata_il=? WHERE traduzione_id=? AND stato='in_corso'",(now(),row['id']))
                    connection.execute("UPDATE corpus_traduzioni SET stato='in_attesa',errore='',aggiornata_il=? WHERE id=?",(now(),row['id']))
                    connection.execute("INSERT INTO corpus_traduzioni_eventi(traduzione_id,codice,creato_il) VALUES(?,?,?)",(row['id'],'ripresa_esplicita',now()))
                return row['id']
            if not prepared or prepared['sha256_originale']!=source_sha or not prepared['segmenti']:
                raise ValueError("Preparazione della traduzione non verificata.")
            identity=uuid4().hex
            connection.execute("INSERT INTO corpus_traduzioni VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(identity,sid,source_sha,language,'it',prepared['modello'],prepared['revisione'],prepared['sha256_modello'],prepared['motore'],'in_attesa',len(prepared['segmenti']),'',now(),now()))
            for number,part in enumerate(prepared['segmenti']):
                connection.execute("INSERT INTO corpus_traduzioni_segmenti(traduzione_id,numero,inizio,fine,source_sha256,stato,aggiornata_il) VALUES(?,?,?,?,?,'in_attesa',?)",(identity,number,part['inizio'],part['fine'],part['sha256'],now()))
            connection.execute("INSERT INTO corpus_traduzioni_eventi(traduzione_id,codice,creato_il) VALUES(?,?,?)",(identity,'richiesta_esplicita',now()))
            return identity

    def get(self, sid, identity, *, segments=False):
        with self.connect() as connection:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='corpus_traduzioni'").fetchone():
                raise KeyError("Traduzione non presente nello studio.")
            row=connection.execute("SELECT * FROM corpus_traduzioni WHERE id=? AND sentenza_id=?",(identity,sid)).fetchone()
            if row is None:
                raise KeyError("Traduzione non presente nello studio.")
            result=dict(row)
            result['completati']=connection.execute("SELECT count(*) FROM corpus_traduzioni_segmenti WHERE traduzione_id=? AND stato='completo'",(identity,)).fetchone()[0]
            result['avvisi']=connection.execute("SELECT count(*) FROM corpus_traduzioni_segmenti WHERE traduzione_id=? AND avviso<>''",(identity,)).fetchone()[0]
            if segments:
                result['segmenti']=[dict(x) for x in connection.execute("SELECT * FROM corpus_traduzioni_segmenti WHERE traduzione_id=? ORDER BY numero",(identity,))]
            return result

    def claim(self, sid, identity):
        with self.connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job=connection.execute("SELECT * FROM corpus_traduzioni WHERE id=? AND sentenza_id=?",(identity,sid)).fetchone()
            if not job:
                raise KeyError("Traduzione non presente nello studio.")
            if job['stato'] in {'completa','errore'}:
                return None
            active=connection.execute("SELECT * FROM corpus_traduzioni_segmenti WHERE traduzione_id=? AND stato='in_corso'",(identity,)).fetchone()
            if active:
                if datetime.fromisoformat(active['aggiornata_il']) < datetime.now(timezone.utc)-timedelta(minutes=5):
                    connection.execute("UPDATE corpus_traduzioni SET stato='errore',errore='lavorazione_interrotta',aggiornata_il=? WHERE id=?",(now(),identity))
                    connection.execute("INSERT INTO corpus_traduzioni_eventi(traduzione_id,codice,creato_il) VALUES(?,?,?)",(identity,'lavorazione_interrotta',now()))
                return None
            row=connection.execute("SELECT * FROM corpus_traduzioni_segmenti WHERE traduzione_id=? AND stato='in_attesa' ORDER BY numero LIMIT 1",(identity,)).fetchone()
            if not row:
                return None
            token=uuid4().hex
            connection.execute("UPDATE corpus_traduzioni_segmenti SET stato='in_corso',claim_token=?,aggiornata_il=? WHERE traduzione_id=? AND numero=?",(token,now(),identity,row['numero']))
            connection.execute("UPDATE corpus_traduzioni SET stato='in_corso',aggiornata_il=? WHERE id=?",(now(),identity))
            return {**dict(row),'claim_token':token}

    def complete(self, sid, identity, part, translated):
        with self.connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            job=connection.execute("SELECT * FROM corpus_traduzioni WHERE id=? AND sentenza_id=?",(identity,sid)).fetchone()
            if not job or job['stato']!='in_corso':
                raise ValueError("Lavorazione non più attiva.")
            if any(job[key]!=translated[key] for key in ('modello','revisione','sha256_modello','motore')):
                raise ValueError("Il modello è cambiato durante la traduzione.")
            if translated['sha256_originale']!=part['source_sha256']:
                raise ValueError("Il segmento originale è cambiato.")
            cursor=connection.execute("UPDATE corpus_traduzioni_segmenti SET stato='completo',testo_tradotto=?,output_sha256=?,avviso=?,claim_token='',aggiornata_il=? WHERE traduzione_id=? AND numero=? AND stato='in_corso' AND claim_token=?",(translated['testo'],translated['sha256_traduzione'],' '.join(translated.get('avvisi',[])),now(),identity,part['numero'],part['claim_token']))
            if cursor.rowcount!=1:
                raise ValueError("Segmento già elaborato da un altro processo.")
            pending=connection.execute("SELECT count(*) FROM corpus_traduzioni_segmenti WHERE traduzione_id=? AND stato<>'completo'",(identity,)).fetchone()[0]
            connection.execute("UPDATE corpus_traduzioni SET stato=?,aggiornata_il=? WHERE id=?",('in_corso' if pending else 'completa',now(),identity))

    def fail(self, sid, identity, code):
        with self.connect(write=True) as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor=connection.execute("UPDATE corpus_traduzioni SET stato='errore',errore=?,aggiornata_il=? WHERE id=? AND sentenza_id=? AND stato<>'completa'",(code,now(),identity,sid))
            if cursor.rowcount:
                connection.execute("INSERT INTO corpus_traduzioni_eventi(traduzione_id,codice,creato_il) VALUES(?,?,?)",(identity,code,now()))
