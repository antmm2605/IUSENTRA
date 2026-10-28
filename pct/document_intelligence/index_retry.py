"""Riacquisizione dell'indice senza moltiplicare i documenti sorgente."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pct.sync import FileLock

def index_source(service: Any, source: Any, records: list[Any], user_context: object) -> Any:
    """La stessa impronta nello stesso fascicolo conserva il proprio record."""
    # Two workers may have fetched the same empty list. Serialize the decision
    # across processes and refresh after taking the lock before creating a record.
    lock_identity = "\0".join((source.tenant_id, source.fascicolo_id, source.sha256 or source.source_id))
    key = hashlib.sha256(lock_identity.encode()).hexdigest()
    json_backend = getattr(service.repository, "backend_kind", "") == "json"
    # JSON repositories share one file across cases; different hashes must not
    # write separate stale snapshots of that file concurrently.
    lock_name = "json-store" if json_backend else key
    lock = service.repository.storage_root / ".iu-index-locks" / lock_name
    with FileLock(str(lock)):
        if json_backend:
            path = service.repository.json_path
            if path.exists() and not isinstance(json.loads(path.read_text(encoding="utf-8")), dict):
                raise ValueError("Archivio documentale JSON non valido")
            service.repository._data = service.repository._load_json()
        current = service.list_fascicolo_documents(source.tenant_id, source.fascicolo_id, user_context)
        return _index_source_locked(service, source, current, user_context)


def _index_source_locked(service: Any, source: Any, records: list[Any], user_context: object) -> Any:
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
