"""Consegna governata dei soli passaggi SQL provati al nuovo embedder."""
from __future__ import annotations

from pct import embeddinggemma2, local_embedding_index
from pct.rag_source_provenance import checked_rows


def verified_for_embedding(conn, rows, *, verifier):
    if not callable(verifier):
        raise ValueError("Riscontro delle fonti SQL obbligatorio prima dell'indicizzazione")
    accepted = checked_rows(conn, rows, verifier=verifier, model=embeddinggemma2.MODEL)
    verified_ids = {row["id"] for row in accepted}
    current_verified = set()
    rejected = changed = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in rows:
            current = conn.execute("""SELECT c.text,c.metadata_json,d.sha256 FROM rag_chunks c
                JOIN rag_documents d ON d.id=c.document_id WHERE c.id=?""", (row["id"],)).fetchone()
            if not current or tuple(current) != (row["text"], row.get("metadata_json"), row["document_sha256"]):
                changed += 1
                continue
            if row["id"] in verified_ids:
                current_verified.add(row["id"])
                # Nuovo riscontro del percorso degli eventi: un esito negativo
                # precedente non impedisce la ripresa della medesima fonte.
                conn.execute("""UPDATE rag_embedding_generations SET status='building',reason=NULL
                    WHERE chunk_id=? AND model=? AND status='invalid' AND reason LIKE 'source_provenance:%'""",
                    (row["id"], embeddinggemma2.MODEL))
                continue
            reason = conn.execute("SELECT reason FROM rag_source_current WHERE chunk_id=? AND model=?",
                                  (row["id"], embeddinggemma2.MODEL)).fetchone()
            if not reason or not reason[0]:
                raise ValueError("Esclusione della fonte priva di causa persistente")
            conn.execute("""INSERT INTO rag_embedding_generations
                (chunk_id,model,text_sha256,document_sha256,status,reason,segment_count,segment_chars)
                VALUES (?,?,?,?,?,?,0,?) ON CONFLICT(chunk_id,model) DO UPDATE SET
                text_sha256=excluded.text_sha256,document_sha256=excluded.document_sha256,
                status=excluded.status,reason=excluded.reason""",
                (row["id"], embeddinggemma2.MODEL, local_embedding_index.fingerprint(row["text"]),
                 row["document_sha256"], "invalid", "source_provenance:"+reason[0],
                 local_embedding_index.SEGMENT_CHARS))
            rejected += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return [row for row in accepted if row["id"] in current_verified], rejected, changed
