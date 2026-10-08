"""Indice locale versionato nel repository RAG SQLite del singolo studio.

Non rilegge documenti e non modifica i vettori precedenti. I segmenti sono
derivati esclusivamente dai chunk SQL e conservano documento, pagina e impronta.
La migrazione storica è esplicita; il percorso ordinario riceve solo i pending.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
import sqlite3
import struct
import time
from typing import Callable

from pct import embeddinggemma2

SEGMENT_CHARS = 768


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pack_vector(vector) -> bytes:
    if len(vector) != 768 or not all(math.isfinite(value) for value in vector):
        raise ValueError("Vettore locale non valido")
    if not 0.999 <= sum(value * value for value in vector) <= 1.001:
        raise ValueError("Vettore locale non normalizzato")
    return struct.pack("<768f", *vector)


def prepare_binary_vectors(conn, *, limit=2048) -> int:
    """Solo migrazione esplicita: cache numerica della medesima generazione.

    Nessuna inferenza, modifica della fonte o quantizzazione dei pesi.
    Un dato corrotto impedisce il checkpoint senza nasconderlo.
    """
    prepared = 0
    while prepared < limit:
        rows = conn.execute("""
            SELECT s.chunk_id,s.ordinal,s.embedding_json
            FROM rag_embedding_segments s JOIN rag_embedding_generations g
                ON g.chunk_id=s.chunk_id AND g.model=s.model
            WHERE s.model=? AND g.status='embedded' AND s.embedding_f32 IS NULL
            ORDER BY s.chunk_id,s.ordinal LIMIT ?
        """, (embeddinggemma2.MODEL, min(32, limit - prepared))).fetchall()
        if not rows:
            break
        updates = [(pack_vector(json.loads(row[2])), row[0], embeddinggemma2.MODEL, row[1]) for row in rows]
        with conn:
            conn.executemany("""
                UPDATE rag_embedding_segments SET embedding_f32=?
                WHERE chunk_id=? AND model=? AND ordinal=? AND embedding_f32 IS NULL
            """, updates)
        prepared += len(updates)
    return prepared


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rag_embedding_generations (
            chunk_id TEXT NOT NULL REFERENCES rag_chunks(id) ON DELETE CASCADE,
            model TEXT NOT NULL,
            text_sha256 TEXT NOT NULL,
            document_sha256 TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            segment_count INTEGER NOT NULL DEFAULT 0,
            segment_chars INTEGER NOT NULL DEFAULT 3200,
            PRIMARY KEY(chunk_id, model)
        );
        CREATE TABLE IF NOT EXISTS rag_embedding_segments (
            chunk_id TEXT NOT NULL,
            model TEXT NOT NULL,
            ordinal INTEGER NOT NULL,
            text TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            PRIMARY KEY(chunk_id, model, ordinal),
            FOREIGN KEY(chunk_id, model)
                REFERENCES rag_embedding_generations(chunk_id, model) ON DELETE CASCADE
        );
    """)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(rag_embedding_generations)")}
    if "segment_chars" not in columns:
        conn.execute("ALTER TABLE rag_embedding_generations ADD COLUMN segment_chars INTEGER NOT NULL DEFAULT 3200")
        conn.commit()
    segment_columns = {row[1] for row in conn.execute("PRAGMA table_info(rag_embedding_segments)")}
    if "embedding_f32" not in segment_columns:
        conn.execute("ALTER TABLE rag_embedding_segments ADD COLUMN embedding_f32 BLOB")
        conn.commit()


def build_chunks(
    conn: sqlite3.Connection, rows: list[dict], *, split: Callable,
    validate: Callable, client=None, deadline: float | None = None,
) -> dict:
    """Checkpoint atomico per chunk, compresi gli esiti negativi dimostrati.

    L'inferenza avviene fuori dalla transazione. Il confronto sotto write lock
    impedisce di pubblicare il risultato se nel frattempo è cambiata la fonte.
    """
    client = client or embeddinggemma2.LocalEmbeddingClient()
    result = {"embedded": 0, "invalid": 0, "unchanged": 0, "changed_source": 0}
    for row in rows:
        source_text = str(row["text"])
        digest = fingerprint(source_text)
        document_digest = str(row["document_sha256"])
        previous = conn.execute(
            "SELECT text_sha256, document_sha256, status, reason, segment_chars FROM rag_embedding_generations WHERE chunk_id=? AND model=?",
            (row["id"], embeddinggemma2.MODEL),
        ).fetchone()
        matching = previous and tuple(previous)[:2] == (digest, document_digest)
        if matching and previous[3] == "fonte_non_letta" and row.get("parse_state") == "parsed":
            matching = False
        # Limitare il singolo calcolo: la priorità delle query non può interrompere
        # un'inferenza già avviata. La fonte rimane interamente nei suoi segmenti.
        segment_chars = int(previous[4]) if matching else SEGMENT_CHARS
        parts = list(split(source_text, max_chars=segment_chars))
        reason = "fonte_non_letta" if row.get("parse_state") != "parsed" else None
        reason = reason or ("testo_assente" if not parts else None)
        for part in parts:
            reason = reason or validate(part)
        if matching and previous[2] in {"embedded", "invalid"}:
            if previous[2] == "invalid" or not reason:
                result["unchanged"] += 1
                continue
            # Una cache precedente non è una prova di lettura: se il controllo
            # nativo trova testo non affidabile, registrare la causa reale.
            matching = False
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = conn.execute(
                "SELECT c.text, d.sha256, d.parse_state FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id WHERE c.id=?",
                (row["id"],),
            ).fetchone()
            if not current or fingerprint(current[0]) != digest or current[1] != document_digest or current[2] != row.get("parse_state"):
                conn.rollback()
                result["changed_source"] += 1
                continue
            if not matching:
                conn.execute(
                    "DELETE FROM rag_embedding_generations WHERE chunk_id=? AND model=?",
                    (row["id"], embeddinggemma2.MODEL),
                )
                conn.execute(
                    "INSERT INTO rag_embedding_generations (chunk_id,model,text_sha256,document_sha256,status,reason,segment_count,segment_chars) VALUES (?,?,?,?,?,?,?,?)",
                    (row["id"], embeddinggemma2.MODEL, digest, document_digest,
                     "invalid" if reason else "building", reason, 0, segment_chars),
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        if not reason:
            completed = {int(r[0]) for r in conn.execute(
                "SELECT ordinal FROM rag_embedding_segments WHERE chunk_id=? AND model=?",
                (row["id"], embeddinggemma2.MODEL),
            ).fetchall()}
            remaining = [(index, part) for index, part in enumerate(parts, 1) if index not in completed]
            source_changed = False
            for start in range(0, len(remaining), 16):
                if deadline is not None and time.monotonic() >= deadline:
                    error = TimeoutError("Budget del lotto terminato: riprendere la generazione salvata")
                    error.embedding_progress = dict(result)
                    raise error
                batch = remaining[start:start+16]
                vectors = client.embed_texts(embeddinggemma2.MODEL, [p for _, p in batch])["embeddings"]
                if len(vectors) != len(batch):
                    raise ValueError("Risposta embedding incompleta")
                conn.execute("BEGIN IMMEDIATE")
                try:
                    current = conn.execute(
                        "SELECT c.text,d.sha256,d.parse_state FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id WHERE c.id=?",
                        (row["id"],),
                    ).fetchone()
                    if not current or fingerprint(current[0]) != digest or current[1] != document_digest or current[2] != row.get("parse_state"):
                        conn.rollback()
                        source_changed = True
                        break
                    conn.executemany(
                        "INSERT OR REPLACE INTO rag_embedding_segments (chunk_id,model,ordinal,text,embedding_json,embedding_f32) VALUES (?,?,?,?,?,?)",
                        [(row["id"], embeddinggemma2.MODEL, index, part, json.dumps(vector),
                          pack_vector(vector))
                         for (index, part), vector in zip(batch, vectors)],
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
            if source_changed:
                result["changed_source"] += 1
                continue
        # Una generazione incompleta non è consultabile. Pubblicare tutti i suoi
        # segmenti insieme, dopo l'ultimo controllo della fonte sotto write lock.
        conn.execute("BEGIN IMMEDIATE")
        try:
            current = conn.execute(
                "SELECT c.text,d.sha256,d.parse_state FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id WHERE c.id=?",
                (row["id"],),
            ).fetchone()
            if not current or fingerprint(current[0]) != digest or current[1] != document_digest or current[2] != row.get("parse_state"):
                conn.rollback()
                result["changed_source"] += 1
                continue
            if not reason:
                count = conn.execute(
                    "SELECT COUNT(*) FROM rag_embedding_segments WHERE chunk_id=? AND model=?",
                    (row["id"],embeddinggemma2.MODEL),
                ).fetchone()[0]
                if count != len(parts):
                    raise ValueError("Generazione embedding incompleta: riprendere il lotto")
            conn.execute(
                "UPDATE rag_embedding_generations SET status=?,reason=?,segment_count=? WHERE chunk_id=? AND model=?",
                ("invalid" if reason else "embedded", reason, 0 if reason else len(parts),row["id"],embeddinggemma2.MODEL),
            )
            # La generazione candidata ha uno stato proprio: non consumare
            # il lavoro pendente né cambiare i vettori del motore operativo.
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        result["invalid" if reason else "embedded"] += 1
    return result


def pending_condition(conn):
    """La coda candidata dipende dalla propria generazione, mai dallo stato legacy."""
    conn.create_function("rag_text_sha256", 1, fingerprint, deterministic=True)
    proof_changed = ""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rag_source_current'").fetchone():
        # Un nuovo riferimento SQL può rendere verificabile lo stesso testo.
        # Il verificatore sostituisce questa causa una volta esaminato l'evento:
        # un nuovo esito negativo non viene quindi riprovato continuamente.
        proof_changed = """ AND NOT EXISTS (SELECT 1 FROM rag_source_current p
            WHERE p.chunk_id=c.id AND p.model=g.model AND p.verified=0
            AND p.reason IN ('passaggio_rag_modificato','fonte_rag_modificata'))"""
    return """NOT EXISTS (SELECT 1 FROM rag_embedding_generations g
        WHERE g.chunk_id=c.id AND g.model=? AND g.document_sha256=d.sha256
        AND g.text_sha256=rag_text_sha256(c.text)
        """ + proof_changed + """
        AND ((g.status='embedded' AND d.parse_state='parsed')
          OR (g.status='invalid' AND NOT (g.reason='fonte_non_letta' AND d.parse_state='parsed'))))"""


def iter_vector_rows(conn, *, practice_id=None, document_id=None):
    conditions = ["g.model=?", "g.status='embedded'", "g.document_sha256=d.sha256", "d.parse_state='parsed'"]
    params = [embeddinggemma2.MODEL]
    for name, value in (("practice_id", practice_id), ("document_id", document_id)):
        if value:
            conditions.append(f"c.{name}=?")
            params.append(value)
    rows = conn.execute(f"""
        SELECT c.id, c.document_id, c.practice_id, c.section_type, c.ordinal,
            c.page_from, c.page_to, c.metadata_json, c.text AS source_text,
            g.text_sha256, s.ordinal AS segment_ordinal, s.text,
            CASE WHEN s.embedding_f32 IS NULL THEN s.embedding_json END AS embedding_json,
            s.embedding_f32
        FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id
        JOIN rag_embedding_generations g ON g.chunk_id=c.id
        JOIN rag_embedding_segments s ON s.chunk_id=g.chunk_id AND s.model=g.model
        WHERE {' AND '.join(conditions)}
        ORDER BY c.id, s.ordinal
    """, params)
    previous_id = None
    source_hash = None
    for row in rows:
        item = dict(row)
        source_text = item.pop("source_text")
        if item["id"] != previous_id:
            previous_id = item["id"]
            source_hash = fingerprint(source_text)
        if source_hash != item.pop("text_sha256"):
            continue
        # Lo stesso chunk può avere più segmenti: identità e prova sono distinte.
        item["source_chunk_id"] = item["id"]
        item["id"] = f"{item['id']}:{item.pop('segment_ordinal')}"
        yield item


def vector_rows(conn, *, practice_id=None, document_id=None) -> list[dict]:
    return list(iter_vector_rows(conn, practice_id=practice_id, document_id=document_id))


def ranked_rows(conn, query_vector, *, practice_id=None, document_id=None, limit=24):
    """Un risultato per chunk, numerico e a memoria limitata, senza letture fonte."""
    import numpy as np
    query = np.asarray(query_vector, dtype=np.float64)
    query_norm = np.linalg.norm(query)

    def ranked_chunks():
        best = None
        for payload in iter_vector_rows(conn, practice_id=practice_id, document_id=document_id):
            binary = payload.pop("embedding_f32")
            encoded = payload.pop("embedding_json")
            vector = (np.frombuffer(binary, dtype="<f4") if binary is not None
                      else np.asarray(json.loads(encoded), dtype=np.float64))
            if vector.shape != (768,) or not np.isfinite(vector).all():
                raise ValueError("Vettore locale non valido: riconvalidare il checkpoint")
            norm = np.linalg.norm(vector)
            payload["vector_score"] = float(np.dot(query, vector) / (query_norm * norm)) if norm and query_norm else 0.0
            payload["segment_id"] = payload["id"]
            payload["id"] = payload["source_chunk_id"]
            if best is not None and best["id"] != payload["id"]:
                yield best
                best = None
            if best is None or payload["vector_score"] > best["vector_score"]:
                best = payload
        if best is not None:
            yield best

    return heapq.nlargest(limit, ranked_chunks(), key=lambda item: item["vector_score"])
