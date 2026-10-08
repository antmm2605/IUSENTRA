"""Indice RAG incrementale: riusa solo testo SQL corrente del fascicolo ricevuto."""
from __future__ import annotations
from typing import Any


def indicizza_testi_archivio(fascicolo: Any, repository: Any, rag: Any, registro: Any, tenant: str, *, retry_document_ids: set[str] | None = None) -> dict:
    from pct.rag_sql_document import index_sql_text

    fid = str(fascicolo.id)
    pending = registro.da_leggere(tenant, fid, "rag_locale", tipi=("documento",))
    negatives = {
        (row.oggetto_id, row.sha256): row for row in registro.letture(tenant, fid, lettore="rag_locale")
        if row.tipo == "documento" and row.stato == "non_leggibile"
    }
    current_ids = {str(doc.id): doc for doc in fascicolo.documenti}
    if not pending and not negatives and not retry_document_ids:
        return {"fascicolo_id": fid, "file_reads": 0, "indexed": 0, "waiting_for_text": 0, "chunks": 0}
    ready = {}
    for record in sorted(repository.list_documents(tenant, fid), key=lambda row: str(row.updated_at), reverse=True):
        if str(record.status) == "ready":
            ready.setdefault(record.sha256, record)
    # Una nuova estrazione SQL è un nuovo riscontro anche con file invariato.
    # Lo stesso esito negativo non deve diventare un retry continuo.
    recoveries = []
    if negatives:
        for obj in registro.oggetti(tenant, fid):
            previous = negatives.get((obj.oggetto_id, obj.impronta))
            record = ready.get(obj.sha256)
            if previous and record and previous.sha256 == obj.impronta and (
                previous.esito.get("version_id") != record.current_version_id
                or previous.esito.get("document_ai_id") != record.id
            ):
                recoveries.append(obj)
    pending = list({obj.oggetto_id: obj for obj in [*pending, *recoveries]}.values())
    if retry_document_ids:
        pending = list({obj.oggetto_id: obj for obj in [*pending, *[obj for obj in registro.oggetti(tenant, fid) if obj.tipo == "documento" and obj.oggetto_id in retry_document_ids]]}.values())
    pending = [obj for obj in pending if obj.oggetto_id in current_ids and obj.presente]
    report = {"fascicolo_id": fid, "file_reads": 0, "indexed": 0, "waiting_for_text": 0, "chunks": 0}
    if not pending:
        return report
    for obj in pending:
        record = ready.get(obj.sha256)
        extracted = repository.get_extracted_text(tenant, fid, record.id, record.current_version_id) if record else None
        outcome = index_sql_text(rag, tenant=tenant, fid=fid, sid=obj.oggetto_id,
            title=str(current_ids[obj.oggetto_id].nome), sha256=obj.sha256,
            record=record, extracted=extracted, backend=repository.backend_kind, force=True)
        reason = outcome.get("reason")
        if reason:
            registro.segna_letto(tenant, fid, obj, "rag_locale", stato="non_leggibile", esito={
                "motivo": reason, "fonte": "archivio_sql", "document_ai_id": record.id if record else "",
                "version_id": record.current_version_id if record else "",
            })
            report["waiting_for_text"] += 1
            continue
        if outcome.get("status") not in {"indexed", "skipped"}:
            report["waiting_for_text"] += 1
            continue
        registro.segna_letto(tenant, fid, obj, "rag_locale", esito={"fonte": "archivio_sql", "document_id": outcome["document_id"], "version_id": record.current_version_id})
        report["indexed"] += 1
        report["chunks"] += int(outcome.get("chunk_count") or 0)
    return report


def aggiorna_rag_da_archivio(fascicolo: Any, registro: Any) -> dict:
    from lex.providers.local_ai_service import get_local_ai_service
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id
    tenant = document_ai_tenant_id()
    # Stessa istanza e configurazione SQL tenant-aware del retrieval Lex.
    # Non costruire un secondo servizio con impostazioni globali di ripiego.
    rag = get_local_ai_service()
    repository = build_document_ai_service().repository
    if repository.backend_kind not in {"sqlite", "postgresql"}:
        raise ValueError("Il RAG richiede testo corrente da SQL")
    report = indicizza_testi_archivio(fascicolo, repository, rag, registro, tenant)
    with rag._connect() as conn:
        pending = rag._pending_chunks_count(conn, practice_id=str(fascicolo.id))
    if pending:
        report["embeddings"] = rag.embed_all_pending_chunks(practice_id=str(fascicolo.id), batch_size=32, max_batches=128)
        if report["embeddings"].get("status") != "ready" or report["embeddings"].get("pending_remaining"):
            raise RuntimeError("Indicizzazione semantica del fascicolo non terminata")
    return report
