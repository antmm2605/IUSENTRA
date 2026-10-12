"""Proiezione degli esiti SQL delle fonti, senza lettura del contenuto."""
from __future__ import annotations

from pct.document_intelligence.indexer import _state_for_source, build_lex_indexing_summary
from pct.document_intelligence.index_outcomes import source_identity
from pct.registro_letture import versione_lettore


def summary_with_registered_outcomes(service, tenant_id, fascicolo_id, sources, context):
    from web.services.registro_letture_runtime import registro_corrente

    summary = service.build_lex_indexing_summary(tenant_id, fascicolo_id, sources, context)
    try:
        registro = registro_corrente(sola_lettura=True)
    except FileNotFoundError:
        readings = []
    else:
        try:
            readings = registro.letture(tenant_id, fascicolo_id, lettore="indice_documentale")
        finally:
            registro.close()
    version = versione_lettore("indice_documentale")
    errors = {
        (reading.oggetto_id, reading.sha256): reading
        for reading in readings
        if reading.tipo == "documento" and reading.stato == "errore"
        and reading.versione_lettore == version
    }
    if not errors and not summary.errors:
        return summary
    records = service.list_fascicolo_documents(tenant_id, fascicolo_id, context)
    failures = []
    for source in sources:
        if _state_for_source(source, records) == "ready":
            continue
        document_id = str(source.metadata.get("documento_id") or source.source_id)
        reading = errors.get((document_id, source.sha256))
        matching = [record for record in records
                    if record.tenant_id == tenant_id and record.fascicolo_id == fascicolo_id
                    and source.sha256 and record.sha256 == source.sha256 and record.status == "error"]
        if matching:
            record = max(matching, key=lambda item: (item.updated_at, item.id))
            outcome = service.repository.latest_processing_error(tenant_id, fascicolo_id, record.id, record.current_version_id)
        elif reading is not None:
            outcome = {"error_code": str(reading.esito.get("error_code") or "source_processing_failed"),
                       "message": str(reading.esito.get("motivo") or "Lettura precedente non completata.")}
        else:
            continue
        failures.append({**source_identity(source), **outcome, "document_id": document_id,
                         "filename": source.filename})
    if not failures:
        return summary
    return build_lex_indexing_summary(sources=sources, records=records, source_errors=failures,
        extra_warnings=[f"{item['filename']}: {item['message']}" for item in failures])
