"""Indice RAG incrementale: riusa solo testo SQL corrente del fascicolo ricevuto."""
from __future__ import annotations
from pathlib import Path
from typing import Any


def indicizza_testi_archivio(fascicolo: Any, repository: Any, rag: Any, registro: Any, tenant: str, *, retry_document_ids: set[str] | None = None) -> dict:
    fid = str(fascicolo.id)
    pending = registro.da_leggere(tenant, fid, "rag_locale", tipi=("documento",))
    if retry_document_ids:
        pending = list({obj.oggetto_id: obj for obj in [*pending, *[obj for obj in registro.oggetti(tenant, fid) if obj.tipo == "documento" and obj.oggetto_id in retry_document_ids]]}.values())
    current_ids = {str(doc.id): doc for doc in fascicolo.documenti}
    pending = [obj for obj in pending if obj.oggetto_id in current_ids and obj.presente]
    report = {"fascicolo_id": fid, "file_reads": 0, "indexed": 0, "waiting_for_text": 0, "chunks": 0}
    if not pending:
        return report
    ready = {}
    for record in sorted(repository.list_documents(tenant, fid), key=lambda row: str(row.updated_at), reverse=True):
        if str(record.status) == "ready":
            ready.setdefault(record.sha256, record)
    for obj in pending:
        record = ready.get(obj.sha256)
        extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id) if record else None
        text = str(getattr(extracted, "text", "") or "").strip()
        engine = str(getattr(extracted, "extraction_engine", "") or "")
        if not text or text.startswith("PCTENC") or "binary-best-effort" in engine or engine == "email.message":
            report["waiting_for_text"] += 1
            continue
        pages = [{"page_number": page.page_number, "text": page.text} for page in extracted.pages]
        outcome = rag.index_text_document(source_type="fascicolo_documento", source_id=obj.oggetto_id,
            practice_id=fid, title=str(current_ids[obj.oggetto_id].nome), text=text, pages=pages,
            metadata={"tenant_id": tenant, "source_document_id": obj.oggetto_id, "content_sha256": obj.sha256,
                "document_ai_id": record.id, "version_id": record.current_version_id, "extraction_engine": engine,
                "source_of_truth": repository.backend_kind, "read_mode": "sql_text_only"}, force=True)
        if outcome.get("status") not in {"indexed", "skipped"}:
            report["waiting_for_text"] += 1
            continue
        registro.segna_letto(tenant, fid, obj, "rag_locale", esito={"fonte": "archivio_sql", "document_id": outcome["document_id"], "version_id": record.current_version_id})
        report["indexed"] += 1
        report["chunks"] += int(outcome.get("chunk_count") or 0)
    return report


def aggiorna_rag_da_archivio(fascicolo: Any, registro: Any) -> dict:
    from flask import current_app, g
    from pct.local_ai import LocalAIService
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id
    paths = dict(getattr(g, "data_paths", {}) or {})
    tenant = document_ai_tenant_id()
    db_path = paths.get("LOCAL_AI_DB")
    if not db_path:
        raise ValueError("Percorso RAG dello studio non disponibile")
    cfg = current_app.config
    rag = LocalAIService(db_path=str(db_path), policy_path=cfg.get("LOCAL_AI_POLICY", "config/ai-policy.json"),
        config_path=paths.get("STUDIO_CONFIG", cfg.get("STUDIO_CONFIG", "config/studio.json")),
        app_root=str(Path(__file__).resolve().parents[2]),
        models_path=paths.get("LOCAL_AI_MODELS_DIR", str(Path(db_path).parent/"models")))
    repository = build_document_ai_service().repository
    if repository.backend_kind not in {"sqlite", "postgresql"}:
        raise ValueError("Il RAG richiede testo corrente da SQL")
    with rag._connect() as conn:
        retry_ids = {row[0] for row in conn.execute("SELECT DISTINCT d.source_id FROM rag_documents d JOIN rag_chunks c ON c.document_id=d.id WHERE d.practice_id=? AND d.source_type='fascicolo_documento' AND c.embedding_state='invalid'", (str(fascicolo.id),))}
    report = indicizza_testi_archivio(fascicolo, repository, rag, registro, tenant, retry_document_ids=retry_ids)
    with rag._connect() as conn:
        pending = rag._pending_chunks_count(conn, practice_id=str(fascicolo.id))
    if pending:
        report["embeddings"] = rag.embed_all_pending_chunks(practice_id=str(fascicolo.id), batch_size=32, max_batches=128)
        if report["embeddings"].get("status") != "ready" or report["embeddings"].get("pending_remaining"):
            raise RuntimeError("Indicizzazione semantica del fascicolo non terminata")
    return report
