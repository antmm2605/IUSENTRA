"""Recupero esplicito della provenienza storica, solo da inventario e testo SQL."""
from __future__ import annotations

import hashlib
import json

from pct.document_intelligence.read_view import SQLDocumentAIReader, source_snapshot
from pct.rag_source_provenance import verify_sources


def recover_sql_proofs(rows, *, tenant, core):
    recovered = []
    with source_snapshot(core) as snapshot:
        reader = SQLDocumentAIReader(snapshot)
        for row in rows:
            meta = json.loads(row.get("metadata_json") or "{}")
            if row.get("source_type") != "fascicolo_documento" or meta.get("tenant_id") not in (None, "", tenant):
                continue
            # Una prova precedente discordante non viene riscritta per farla
            # risultare valida: le variazioni seguono gli eventi nativi.
            if any(meta.get(key) for key in ("content_sha256", "document_ai_id", "version_id")):
                continue
            fid, sid = str(row.get("practice_id") or ""), str(row.get("source_id") or "")
            record = snapshot.conn.execute("SELECT documenti_json FROM fascicoli WHERE id=?", (fid,)).fetchone()
            inventory = json.loads(record["documenti_json"] or "[]") if record else []
            source = next((doc for doc in inventory if str(doc.get("id") or "") == sid), None)
            digest = str((source or {}).get("hash_contenuto_sha256") or (source or {}).get("hash_sha256") or "")
            if len(digest) != 64 or meta.get("source_document_id") not in (None, "", sid):
                continue
            for document in reader.list_documents(tenant, fid):
                if document.status != "ready" or document.sha256 != digest:
                    continue
                proposed = {**meta, "tenant_id": tenant, "source_document_id": sid,
                    "content_sha256": digest, "document_ai_id": document.id,
                    "version_id": document.current_version_id, "source_of_truth": reader.backend_kind,
                    "read_mode": "sql_text_only"}
                candidate = {**row, "metadata_json": json.dumps(proposed, ensure_ascii=False, sort_keys=True)}
                accepted, _ = verify_sources([candidate], tenant=tenant,
                    source_lookup=lambda *args: source, repository=reader)
                if accepted:
                    recovered.append(candidate)
                    break
    return recovered


def record_recovered_proofs(conn, rows, recovered):
    """Audit e metadati insieme; non modifica testo, importi o vettori precedenti."""
    originals = {row["id"]: row for row in rows}
    conn.execute("""CREATE TABLE IF NOT EXISTS rag_source_reconciliation (
        chunk_id TEXT NOT NULL,before_sha256 TEXT NOT NULL,after_sha256 TEXT NOT NULL,
        before_json TEXT NOT NULL,after_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(chunk_id,before_sha256,after_sha256))""")
    conn.commit()
    changed = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for row in recovered:
            previous = originals[row["id"]]
            before, after = previous.get("metadata_json") or "", row["metadata_json"]
            updated = conn.execute("""UPDATE rag_chunks SET metadata_json=?
                WHERE id=? AND text=? AND COALESCE(metadata_json,'')=?""",
                (after, row["id"], previous["text"], before))
            if updated.rowcount != 1:
                continue
            conn.execute("""INSERT OR IGNORE INTO rag_source_reconciliation
                (chunk_id,before_sha256,after_sha256,before_json,after_json) VALUES (?,?,?,?,?)""",
                (row["id"], hashlib.sha256(before.encode()).hexdigest(),
                 hashlib.sha256(after.encode()).hexdigest(), before, after))
            changed += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return changed
