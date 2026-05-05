"""Helper di versionamento documentale AI."""

from __future__ import annotations

from pathlib import PurePosixPath

from .models import DOCUMENT_AI_SOURCES, DocumentAIVersion, new_id, utc_now
from .security import DocumentAIValidationError, sanitize_filename


def next_version_number(existing_versions: list[DocumentAIVersion]) -> int:
    if not existing_versions:
        return 1
    return max(version.version_number for version in existing_versions) + 1


def validate_source(source: str) -> str:
    clean = str(source or "").strip()
    if clean not in DOCUMENT_AI_SOURCES:
        raise DocumentAIValidationError("Sorgente versione documento AI non valida.")
    return clean


def build_document_storage_relative_path(
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    version_number: int,
    safe_filename: str,
) -> str:
    tenant = _safe_segment(tenant_id, "tenant")
    fascicolo = _safe_segment(fascicolo_id, "fascicolo")
    document = _safe_segment(document_id, "documento")
    version = _safe_version(version_number)
    filename = sanitize_filename(safe_filename)
    return str(PurePosixPath(tenant, "fascicoli", fascicolo, "documenti_ai", document, version, filename))


def build_extracted_text_relative_path(
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    version_number: int,
) -> str:
    tenant = _safe_segment(tenant_id, "tenant")
    fascicolo = _safe_segment(fascicolo_id, "fascicolo")
    document = _safe_segment(document_id, "documento")
    version = _safe_version(version_number)
    return str(PurePosixPath(tenant, "fascicoli", fascicolo, "documenti_ai", document, version, "extracted_text.json"))


def build_initial_version(
    *,
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    storage_path: str,
    sha256: str,
    created_by: str,
) -> DocumentAIVersion:
    return DocumentAIVersion(
        id=new_id("docaiver"),
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        document_id=document_id,
        version_number=1,
        source=validate_source("upload"),
        storage_path=storage_path,
        extracted_text_path=None,
        pdf_preview_path=None,
        sha256=sha256,
        created_by=created_by,
        created_at=utc_now(),
    )


def _safe_segment(value: str, label: str) -> str:
    clean = str(value or "").strip()
    if not clean or clean in {".", ".."} or "/" in clean or "\\" in clean:
        raise DocumentAIValidationError(f"Identificativo {label} non valido.")
    return clean


def _safe_version(version_number: int) -> str:
    try:
        number = int(version_number)
    except (TypeError, ValueError) as exc:
        raise DocumentAIValidationError("Numero versione non valido.") from exc
    if number < 1:
        raise DocumentAIValidationError("Numero versione non valido.")
    return f"v{number}"
