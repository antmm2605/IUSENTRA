"""Helper di versionamento documentale AI."""

from __future__ import annotations

from .models import DocumentAIVersion, new_id, utc_now


def next_version_number(existing_versions: list[DocumentAIVersion]) -> int:
    if not existing_versions:
        return 1
    return max(version.version_number for version in existing_versions) + 1


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
        source="upload",
        storage_path=storage_path,
        extracted_text_path=None,
        pdf_preview_path=None,
        sha256=sha256,
        created_by=created_by,
        created_at=utc_now(),
    )
