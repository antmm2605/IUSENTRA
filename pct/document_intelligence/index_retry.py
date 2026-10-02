"""Riacquisizione dell'indice senza moltiplicare i documenti sorgente."""

from __future__ import annotations

from typing import Any

def index_source(service: Any, source: Any, records: list[Any], user_context: object) -> Any:
    """La stessa impronta nello stesso fascicolo conserva il proprio record."""
    matching = [record for record in records if source.sha256
                and record.sha256 == source.sha256
                and record.tenant_id == source.tenant_id
                and record.fascicolo_id == source.fascicolo_id]
    if matching:
        record = max(matching, key=lambda item: (bool(item.current_version_id), item.updated_at, item.id))
        service.reacquire_existing_version(source.tenant_id, source.fascicolo_id,
                                          record.id, source.read_bytes(), user_context)
        return service.repository.get_document(source.tenant_id, source.fascicolo_id, record.id)
    result = service.upload_document_bytes_for_fascicolo(
        tenant_id=source.tenant_id, fascicolo_id=source.fascicolo_id,
        filename=source.safe_filename if source.file_type == "bin" else source.filename,
        content=source.read_bytes(), mime_type=source.mime_type,
        user_context=user_context, source_metadata=source.public_metadata())
    return result.document


def native_engine_is_current(source_names: set[str], engine: str) -> bool:
    for file_type in ("ods", "odp", "pptx"):
        if any(name.endswith((f".{file_type}", f".{file_type}.bin")) for name in source_names):
            return engine == f"{file_type}.native-xml-v1"
    if any(name.endswith((".webp", ".webp.bin")) for name in source_names):
        return engine != "bin.binary-best-effort"
    return True
