"""Unico ingresso RAG per il documento originale già letto dal repository SQL."""
from __future__ import annotations


def index_sql_text(rag, *, tenant, fid, sid, title, sha256, record, extracted, backend, force=False):
    from pct.local_ai import _bounded_text_parts, _embedding_validation_reason

    reason = ""
    if backend not in {"sqlite", "postgresql"}:
        reason = "Il documento richiede il repository SQL corrente."
    elif (not record or record.tenant_id != tenant or record.fascicolo_id != fid
          or record.status != "ready" or len(sha256) != 64 or record.sha256 != sha256):
        reason = "Fonte, studio o impronta del documento SQL non concordanti."
    elif (not extracted or extracted.tenant_id != tenant or extracted.fascicolo_id != fid
          or extracted.document_id != record.id or extracted.version_id != record.current_version_id):
        reason = "Estrazione SQL non riferita alla versione corrente della fonte."
    text = str(getattr(extracted, "text", "") or "").strip()
    engine = str(getattr(extracted, "extraction_engine", "") or "")
    if not reason and ("binary-best-effort" in engine or engine == "email.message"):
        reason = "Estrazione non documentale: attesa del testo verificato nel repository SQL."
    if not reason:
        reason = next((error for part in _bounded_text_parts(text, max_chars=3200)
                       if (error := _embedding_validation_reason(part))), None) if text else _embedding_validation_reason(text)
    if not reason and extracted.pages:
        page_text = "".join(str(page.text or "") for page in extracted.pages)
        if "".join(page_text.split()) != "".join(text.split()):
            reason = "Le pagine SQL non coprono il testo completo della fonte."
    if reason:
        return {"status": "waiting_for_text", "reason": reason}
    proof = {"tenant_id": tenant, "source_document_id": sid, "content_sha256": sha256,
             "document_ai_id": record.id, "version_id": record.current_version_id,
             "extraction_engine": engine, "source_of_truth": backend, "read_mode": "sql_text_only"}
    outcome = rag.index_text_document(source_type="fascicolo_documento", source_id=sid,
        practice_id=fid, title=title, text=text,
        pages=[{"page_number": page.page_number, "text": page.text} for page in extracted.pages],
        metadata=proof, force=force)
    return {**outcome, "proof": proof}


def index_original_source(fascicolo, repository, rag, *, tenant, metadata):
    """Identificatore originale o impronta unica: nessuna associazione per nome."""
    if metadata.get("tenant_id") != tenant:
        return {"status": "waiting_for_text", "reason": "Studio della fonte discordante."}
    digest = str(metadata.get("sha256") or "")
    candidates = [doc for doc in fascicolo.documenti if digest and
                  (getattr(doc, "hash_contenuto_sha256", "") or getattr(doc, "hash_sha256", "")) == digest]
    source_id = str(metadata.get("source_id") or metadata.get("source_document_id") or metadata.get("documento_id") or "")
    if source_id:
        candidates = [doc for doc in candidates if str(doc.id) == source_id]
    if len(candidates) != 1:
        return {"status": "waiting_for_text", "reason": "Documento originale assente o non univoco nel fascicolo SQL."}
    doc = candidates[0]
    fid = str(fascicolo.id)
    records = [row for row in repository.list_documents(tenant, fid) if row.status == "ready" and row.sha256 == digest]
    ai_id = str(metadata.get("document_id") or "")
    if ai_id:
        records = [row for row in records if row.id == ai_id]
    if len(records) != 1:
        return {"status": "waiting_for_text", "reason": "Estrazione corrente assente o non univoca nel repository SQL."}
    record = records[0]
    extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id)
    return index_sql_text(rag, tenant=tenant, fid=fid, sid=str(doc.id), title=doc.nome,
                          sha256=digest, record=record, extracted=extracted, backend=repository.backend_kind)
