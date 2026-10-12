"""Identità degli esiti delle fonti, indipendente dal nome visualizzato."""
from __future__ import annotations
from typing import Any
from .sources import DocumentAISource


def source_error_key(value: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(value.get(key) or "") for key in ("tenant_id", "fascicolo_id", "source_id", "sha256"))


def source_identity(source: DocumentAISource) -> dict[str, str]:
    return {"tenant_id": source.tenant_id, "fascicolo_id": source.fascicolo_id,
            "source_id": source.source_id, "sha256": source.sha256}


def source_error(source: DocumentAISource, exc: Exception) -> dict[str, Any]:
    if isinstance(exc, FileNotFoundError):
        code, message = "source_unavailable", "Fonte originale non disponibile nel percorso registrato."
    elif isinstance(exc, PermissionError):
        code, message = "source_access_denied", "Accesso alla fonte originale non consentito."
    else:
        from .security import DocumentAIValidationError
        code = "source_validation_failed" if isinstance(exc, DocumentAIValidationError) else "source_processing_failed"
        message = str(exc) if isinstance(exc, DocumentAIValidationError) else "Indicizzazione della fonte non completata."
    return {**source_identity(source), "document_id": str(source.metadata.get("documento_id") or source.source_id),
            "filename": source.filename, "error_code": code, "message": message}
