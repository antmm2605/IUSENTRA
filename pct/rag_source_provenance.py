"""Riscontro delle citazioni nel SQL corrente, senza aprire gli originali."""
from __future__ import annotations

import hashlib
import json


def verify_current_sql(rows, *, tenant, core):
    """Stesso riscontro per Lex e riconvalida esplicita, nella fotografia nativa."""
    from pct.document_intelligence.read_view import SQLDocumentAIReader, source_snapshot

    cases = {}
    with source_snapshot(core) as snapshot:
        def lookup(expected_tenant, fid, sid):
            if expected_tenant != tenant:
                raise ValueError("Contesto studio discordante")
            if fid not in cases:
                result = snapshot.conn.execute("SELECT documenti_json FROM fascicoli WHERE id=?", (fid,)).fetchone()
                cases[fid] = json.loads(result["documenti_json"] or "[]") if result else []
            return next((doc for doc in cases[fid] if str(doc.get("id") or "") == sid), None)
        return verify_sources(rows, tenant=tenant, source_lookup=lookup,
                              repository=SQLDocumentAIReader(snapshot))


def verify_sources(rows, *, tenant, source_lookup, repository):
    """Lookup tenant-aware forniti dal runtime nativo SQLite/PostgreSQL."""
    if repository.backend_kind not in {"sqlite", "postgresql"}:
        raise ValueError("Le citazioni richiedono il repository SQL corrente")
    accepted, checks, sources, texts = [], [], {}, {}
    for row in rows:
        meta = json.loads(row.get("metadata_json") or "{}")
        if row.get("source_type") != "fascicolo_documento":
            # Una scheda economica derivata non è il passaggio della sentenza
            # originale. Non citarla come prova né ereditare un altro tenant.
            checks.append({"tenant": tenant, "fascicolo_id": str(row.get("practice_id") or ""),
                           "source_id": str(row.get("source_id") or ""), "content_sha256": "",
                           "version_id": "", "chunk_id": row["id"],
                           "reason": "provenienza_sql_non_registrata" if meta.get("tenant_id") != tenant
                           else "fonte_derivata_senza_prova_documentale"})
            continue
        fid, sid = str(row.get("practice_id") or ""), str(row.get("source_id") or "")
        reason, version = "", ""
        if meta.get("tenant_id") != tenant or meta.get("source_document_id") != sid:
            reason = "provenienza_sql_non_registrata"
        key = (fid, sid)
        if key not in sources:
            sources[key] = source_lookup(tenant, fid, sid)
        source = sources[key]
        if not reason and not source:
            reason = "fonte_non_presente_nel_fascicolo_sql"
        digest = str((source or {}).get("hash_contenuto_sha256") or (source or {}).get("hash_sha256") or "")
        if not reason and (len(digest) != 64 or digest != meta.get("content_sha256")):
            reason = "impronta_fonte_cambiata_o_assente"
        document = None
        if not reason:
            document = repository.get_document(tenant, fid, meta.get("document_ai_id"))
            version = str(getattr(document, "current_version_id", "") or "")
            if not document or document.sha256 != digest or document.status != "ready" or version != meta.get("version_id"):
                reason = "estrazione_sql_non_corrente"
        if not reason:
            tkey = (fid, document.id, version)
            if tkey not in texts:
                texts[tkey] = repository.get_extracted_text(tenant, fid, document.id, version)
            extracted = texts[tkey]
            engine = str(getattr(extracted, "extraction_engine", "") or "")
            text = str(getattr(extracted, "text", "") or "")
            if not text or "binary-best-effort" in engine or engine == "email.message":
                reason = "testo_documentale_non_verificato"
            elif not str(row.get("text") or "").strip() or str(row["text"]).strip() not in text:
                reason = "passaggio_non_presente_nel_testo_sql"
        proof = {"tenant": tenant, "fascicolo_id": fid, "source_id": sid,
                 "content_sha256": digest, "version_id": version, "reason": reason}
        proof["chunk_id"] = row["id"]
        checks.append(proof)
        if not reason:
            accepted.append(row)
    return accepted, checks


def checked_rows(conn, rows, *, verifier, model):
    """Riconvalida anche la cache; conserva cause e riscontri nel registro RAG."""
    if not callable(verifier) or not rows:
        return rows
    ids = list({str(row["document_id"]) for row in rows})
    marks = ",".join("?" for _ in ids)
    documents = {row[0]: row for row in conn.execute(
        f"SELECT id,source_type,source_id FROM rag_documents WHERE id IN ({marks})", ids,
    )}
    enriched = [{**row, "source_type": documents[row["document_id"]][1],
                 "source_id": documents[row["document_id"]][2]} for row in rows if row["document_id"] in documents]
    accepted, checks = verifier(enriched)
    conn.execute("""CREATE TABLE IF NOT EXISTS rag_source_checks (
        chunk_id TEXT NOT NULL, model TEXT NOT NULL, proof_sha256 TEXT NOT NULL,
        verified INTEGER NOT NULL, reason TEXT NOT NULL, proof_json TEXT NOT NULL,
        checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(chunk_id,model,proof_sha256))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS rag_source_current (
        chunk_id TEXT NOT NULL, model TEXT NOT NULL, proof_sha256 TEXT NOT NULL,
        verified INTEGER NOT NULL, reason TEXT NOT NULL, proof_json TEXT NOT NULL,
        PRIMARY KEY(chunk_id,model))""")
    # Una modifica locale invalida il riscontro nella stessa transazione,
    # senza rileggere il corpus quando la UI chiede i conteggi. L'audit della
    # prova precedente rimane in rag_source_checks; solo una nuova verifica
    # delle fonti SQL può ripristinare la conferma corrente.
    conn.execute("""CREATE TRIGGER IF NOT EXISTS rag_source_chunk_changed
        AFTER UPDATE OF text,metadata_json,document_id,practice_id ON rag_chunks
        WHEN OLD.text IS NOT NEW.text OR OLD.metadata_json IS NOT NEW.metadata_json
            OR OLD.document_id IS NOT NEW.document_id OR OLD.practice_id IS NOT NEW.practice_id
        BEGIN
            UPDATE rag_source_current SET verified=0,reason='passaggio_rag_modificato'
            WHERE chunk_id=NEW.id;
        END""")
    conn.execute("""CREATE TRIGGER IF NOT EXISTS rag_source_document_changed
        AFTER UPDATE OF sha256,source_type,source_id ON rag_documents
        WHEN OLD.sha256 IS NOT NEW.sha256 OR OLD.source_type IS NOT NEW.source_type
            OR OLD.source_id IS NOT NEW.source_id
        BEGIN
            UPDATE rag_source_current SET verified=0,reason='fonte_rag_modificata'
            WHERE chunk_id IN (SELECT id FROM rag_chunks WHERE document_id=NEW.id);
        END""")
    for check in checks:
        raw = json.dumps(check, sort_keys=True, ensure_ascii=False)
        proof_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        conn.execute("""INSERT OR IGNORE INTO rag_source_checks
            (chunk_id,model,proof_sha256,verified,reason,proof_json) VALUES (?,?,?,?,?,?)""",
            (check["chunk_id"], model, proof_hash, int(not check["reason"]), check["reason"], raw))
        conn.execute("""INSERT INTO rag_source_current
            (chunk_id,model,proof_sha256,verified,reason,proof_json) VALUES (?,?,?,?,?,?)
            ON CONFLICT(chunk_id,model) DO UPDATE SET proof_sha256=excluded.proof_sha256,
                verified=excluded.verified,reason=excluded.reason,proof_json=excluded.proof_json
            WHERE rag_source_current.proof_sha256<>excluded.proof_sha256
                OR rag_source_current.verified<>excluded.verified
                OR rag_source_current.reason<>excluded.reason""",
            (check["chunk_id"], model, proof_hash, int(not check["reason"]), check["reason"], raw))
    conn.commit()
    return accepted


def provenance_snapshot(conn, model):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='rag_source_current'").fetchone():
        return {"checked_chunks": 0, "verified_chunks": 0, "excluded_chunks": 0, "reasons": []}
    groups = conn.execute("""SELECT p.verified,p.reason,COUNT(*) FROM rag_source_current p
        JOIN rag_chunks c ON c.id=p.chunk_id
        WHERE p.model=? GROUP BY p.verified,p.reason""", (model,)).fetchall()
    verified = sum(row[2] for row in groups if row[0])
    excluded = sum(row[2] for row in groups if not row[0])
    return {"checked_chunks": verified + excluded, "verified_chunks": verified,
            "excluded_chunks": excluded,
            "reasons": [{"reason": row[1], "chunks": row[2]} for row in groups if not row[0]]}
