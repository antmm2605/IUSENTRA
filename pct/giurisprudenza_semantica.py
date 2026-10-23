"""Indice candidato delle sentenze: riusa costruzione e vettori del motore giuridico.

Nessuna scrittura nel corpus e nessuna attivazione automatica. La tabella laterale
espone viste di compatibilita al costruttore, senza trasformare sentenze in norme.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from lex.ricerca_giuridica.embedding import EmbedderDomande, OllamaEmbedder
from lex.ricerca_giuridica.indice_vettoriale import IndiceVettoriale, costruisci_indice
from pct.sync import FileLock


def cartella_indice(db):
    path = Path(db).resolve()
    return path.with_name(path.name + ".semantica")


def _hash(text):
    return hashlib.sha256(str(text or "").encode()).hexdigest()


def _connect_ro(path):
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def prepara(db, folder):
    """Snapshot dei soli testi proprietari: massime ufficiali, principi e dispositivo."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    side = sqlite3.connect(folder / "unita.sqlite")
    side.executescript("""
      CREATE TABLE IF NOT EXISTS units (
        id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, sentenza_id INTEGER NOT NULL,
        tipo TEXT NOT NULL, source_id INTEGER NOT NULL, source_sha TEXT NOT NULL,
        titolo TEXT NOT NULL, testo TEXT NOT NULL, seen INTEGER DEFAULT 0);
      CREATE VIEW IF NOT EXISTS normative_chunks AS
        SELECT id, sentenza_id AS document_id, id AS article_id, testo AS chunk_text FROM units;
      CREATE VIEW IF NOT EXISTS normative_documents AS
        SELECT sentenza_id AS id, max(titolo) AS titolo, '' AS numero, '' AS data_atto
        FROM units GROUP BY sentenza_id;
      CREATE VIEW IF NOT EXISTS normative_articles AS
        SELECT id, '' AS article_number, tipo AS article_title FROM units;
    """)
    with _connect_ro(db) as source, side:
        side.execute("UPDATE units SET seen=0")
        sources = [
            (
                "massima",
                "SELECT m.id AS source_id,s.id AS sentenza_id,s.titolo,m.testo FROM massime m JOIN sentenze s ON s.id=m.sentenza_id WHERE m.ufficiale=1",
            ),
            (
                "principio",
                "SELECT p.id AS source_id,s.id AS sentenza_id,s.titolo,p.testo FROM principi_diritto p JOIN sentenze s ON s.id=p.sentenza_id",
            ),
            ("dispositivo", "SELECT id AS source_id,id AS sentenza_id,titolo,esito AS testo FROM sentenze"),
        ]
        for kind, query in sources:
            # L'oggetto/esito OpenGA non entra nell'indice dei contenuti delle decisioni.
            eligible = " NOT EXISTS (SELECT 1 FROM fonti_giurisprudenza f WHERE f.id=s.fonte_id AND f.codice='openga' AND COALESCE(s.testo_integrale_presente,0)=0)"
            if kind == "dispositivo":
                query = (
                    "SELECT s.id AS source_id,s.id AS sentenza_id,s.titolo,s.esito AS testo FROM sentenze s WHERE"
                    + eligible
                )
            else:
                query += (" AND" if " WHERE " in query else " WHERE") + eligible
            for row in source.execute(query):
                raw = str(row["testo"] or "")
                text = " ".join(raw.split())
                if not text:
                    continue
                # Finestre sotto il limite del motore: anche le massime lunghe restano coperte.
                for part, start in enumerate(range(0, len(text), 1600)):
                    segment = text[start : start + 1800]
                    key = f"{kind}:{row['source_id']}:{part}"
                    side.execute(
                        """INSERT INTO units(key,sentenza_id,tipo,source_id,source_sha,titolo,testo,seen)
                      VALUES(?,?,?,?,?,?,?,1) ON CONFLICT(key) DO UPDATE SET
                      sentenza_id=excluded.sentenza_id,source_sha=excluded.source_sha,
                      titolo=excluded.titolo,testo=excluded.testo,seen=1""",
                        (key, row["sentenza_id"], kind, row["source_id"], _hash(raw), row["titolo"] or "", segment),
                    )
                    if start + 1800 >= len(text):
                        break
        side.execute("DELETE FROM units WHERE seen=0")
    return side


class CacheConsultaPubblica:
    """Riuso fra copie dei soli archivi pubblici della Consulta; mai corpus misti."""

    paralleli = 1

    def __init__(self, engine, path, corpus):
        import numpy as np

        self.np = np
        with _connect_ro(corpus) as source:
            non_pubblici = source.execute("""SELECT count(*) FROM sentenze s
                LEFT JOIN fonti_giurisprudenza f ON f.id=s.fonte_id
                WHERE COALESCE(f.codice,'')!='corte_costituzionale'
                   OR COALESCE(s.fonte_ufficiale_confermata,0)!=1
                   OR COALESCE(s.ecli,'') NOT LIKE 'ECLI:IT:COST:%'""").fetchone()[0]
            non_pubblici += source.execute("SELECT count(*) FROM principi_diritto WHERE ufficiale!=1").fetchone()[0]
        if non_pubblici:
            raise ValueError("Cache condivisa rifiutata: corpus non esclusivamente Consulta pubblica")
        self.engine = engine
        self.modello = engine.modello
        self.version = engine.versione()
        if not self.version:
            raise ValueError("Cache pubblica richiede impronta del modello verificata")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB NOT NULL)")

    def versione(self):
        return self.version

    def embed(self, texts):
        np = self.np
        keys = [_hash(self.modello + "|" + self.version + "|" + text) for text in texts]
        vectors = [None] * len(texts)
        with FileLock(str(self.path)), sqlite3.connect(self.path) as c:
            missing = []
            for i, key in enumerate(keys):
                row = c.execute("SELECT vector FROM vectors WHERE key=?", (key,)).fetchone()
                if row:
                    vectors[i] = np.frombuffer(row[0], dtype="<f4").copy()
                else:
                    missing.append(i)
            if missing:
                result = self.engine.embed([texts[i] for i in missing])
                if len(result) != len(missing):
                    raise ValueError("Risposta embedding incompleta")
                for i, vector in zip(missing, result):
                    vector = np.asarray(vector, dtype="<f4")
                    if vector.ndim != 1 or not np.isfinite(vector).all():
                        raise ValueError("Vettore non valido")
                    c.execute("INSERT OR REPLACE INTO vectors VALUES(?,?)", (keys[i], vector.tobytes()))
                    vectors[i] = vector
        return np.asarray(vectors)


def costruisci(db, *, embedder=None, massimo=None, batch=16, folder=None, cache_pubblica=None):
    engine = embedder or OllamaEmbedder()
    if cache_pubblica:
        engine = CacheConsultaPubblica(engine, cache_pubblica, db)
    folder = Path(folder or cartella_indice(db))
    folder.mkdir(parents=True, exist_ok=True)
    with FileLock(str(folder / "costruzione.lock")):
        report_path = folder / "esito-costruzione.json"
        invalid = report_path.with_suffix(".tmp")
        invalid.write_text(
            json.dumps({"corpus": str(Path(db).resolve()), "interrotto_al_massimo": True, "attivato": False})
        )
        invalid.replace(report_path)
        with closing(prepara(db, folder)) as conn:
            result = costruisci_indice(conn, folder / "vettori", engine, massimo=massimo, batch=batch)
            count = conn.execute("SELECT count(*) FROM units").fetchone()[0]
        report = {"corpus": str(Path(db).resolve()), "unita": count, **result.to_dict(), "attivato": False}
        invalid.write_text(json.dumps(report, indent=2))
        invalid.replace(report_path)
        return report


def cerca(db, domanda, *, embedder=None, folder=None, limit=100):
    """Sola lettura; elimina candidati cancellati o cambiati dopo l'indicizzazione."""
    folder = Path(folder or cartella_indice(db))
    report_path = folder / "esito-costruzione.json"
    if not report_path.exists():
        return []
    report_iniziale = report_path.read_bytes()
    if report_path.exists():
        report = json.loads(report_path.read_text())
        if report.get("interrotto_al_massimo"):
            return []
        if report.get("corpus") != str(Path(db).resolve()):
            raise ValueError("Indice appartenente a un altro corpus")
    index = IndiceVettoriale.apri(folder / "vettori")
    if index is None:
        return []
    engine = embedder or OllamaEmbedder(timeout=4, tentativi=1)
    ok, reason = index.verifica_modello(engine.modello, engine.versione())
    if not ok:
        raise ValueError(reason)
    vector = EmbedderDomande(engine).vettore(domanda)
    hits = index.cerca(vector, k=min(2000, max(100, limit * 10)))
    seen = set()
    results = []
    with _connect_ro(folder / "unita.sqlite") as units, _connect_ro(db) as source:
        for unit_id, score in hits:
            row = units.execute("SELECT * FROM units WHERE id=?", (unit_id,)).fetchone()
            if row is None or row["sentenza_id"] in seen:
                continue
            kind = row["tipo"]
            table, field = {
                "massima": ("massime", "testo"),
                "principio": ("principi_diritto", "testo"),
                "dispositivo": ("sentenze", "esito"),
            }[kind]
            original = source.execute(f"SELECT {field} FROM {table} WHERE id=?", (row["source_id"],)).fetchone()
            if original is None or _hash(original[0]) != row["source_sha"]:
                continue
            if not source.execute("SELECT 1 FROM sentenze WHERE id=?", (row["sentenza_id"],)).fetchone():
                continue
            seen.add(row["sentenza_id"])
            results.append((row["sentenza_id"], float(score)))
            if len(results) >= limit:
                break
    if report_path.read_bytes() != report_iniziale:
        return []
    return results


def fondi(lessicali, semantici, *, limit=20):
    """RRF k=60, stessi ranghi del motore norme, deduplicati per sentenza."""
    from lex.ricerca_giuridica.ibrida import RRF_K

    scores = {}
    for ranking in [lessicali, semantici]:
        for rank, sid in enumerate(dict.fromkeys(ranking), 1):
            scores[sid] = scores.get(sid, 0) + 1 / (RRF_K + rank)
    return sorted(scores, key=lambda sid: (-scores[sid], sid))[:limit]


def preserva_lessicali(ranking, lessicali, *, limit):
    """Riserva meta dei posti ai primi risultati esistenti, senza duplicarli.

    La fusione mantiene il proprio ordine e puo promuovere nuove decisioni;
    i risultati lessicali protetti rimpiazzano soltanto la coda non protetta.
    """
    limit = max(1, int(limit))
    ranking = list(dict.fromkeys(ranking))
    protected = list(dict.fromkeys(lessicali))[: limit // 2]
    result = ranking[:limit]
    for sid in protected:
        if sid in result:
            continue
        if len(result) >= limit:
            drop = next((i for i in range(len(result)-1, -1, -1) if result[i] not in protected), None)
            if drop is not None:
                result.pop(drop)
        result.append(sid)
    return result[:limit]
