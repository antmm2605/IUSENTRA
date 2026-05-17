"""Manifest di ingestione tenant-aware per dataset Lex."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from .models import (
    IngestionManifest,
    IngestionManifestDocument,
    StudioDatasetDocument,
    clean_text,
    stable_id,
)
from .privacy import classify_privacy


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_ingestion_manifest(
    tenant_id: str,
    documents: Iterable[StudioDatasetDocument],
    *,
    created_at: str | None = None,
) -> IngestionManifest:
    tenant = clean_text(tenant_id)
    if not tenant:
        raise ValueError("tenant_id obbligatorio per il manifest Lex.")

    rows: list[IngestionManifestDocument] = []
    identity_parts: list[str] = [tenant]
    for document in documents:
        if document.tenant_id != tenant:
            raise ValueError(
                f"Documento {document.document_id!r} fuori tenant: {document.tenant_id!r} != {tenant!r}."
            )
        text = document.all_text()
        privacy = classify_privacy(text)
        page_count = len(document.pages)
        rows.append(
            IngestionManifestDocument(
                tenant_id=tenant,
                document_id=document.document_id,
                title=document.title,
                source_name=document.source_name,
                source_kind=document.source_kind,
                mime_type=document.mime_type,
                fascicolo_id=document.fascicolo_id,
                sha256=document.sha256,
                page_count=page_count,
                text_chars=len(text),
                privacy_classification=privacy,
                metadata={
                    "has_extracted_text": bool(text.strip()),
                    "source_path_sanitized": True,
                },
            )
        )
        identity_parts.extend([document.document_id, document.sha256, document.source_name, str(len(text))])

    manifest_id = stable_id(*identity_parts, prefix="lex-manifest-")
    return IngestionManifest(
        tenant_id=tenant,
        manifest_id=manifest_id,
        created_at=created_at or _utc_now_iso(),
        documents=tuple(rows),
        storage_scope=f"tenant:{tenant}",
        rag_policy={
            "mode": "rag_immediate",
            "description": "I chunk restano nel retrieval tenant-aware e sono usabili subito da Lex.",
            "external_provider_required": False,
        },
        fine_tuning_policy={
            "mode": "supervised_candidates_only",
            "requires_human_review": True,
            "automatic_training": False,
            "external_training": False,
            "notes": "Il manifest non avvia addestramento: prepara solo esempi revisionabili.",
        },
        privacy_policy={
            "tenant_isolation": True,
            "absolute_paths_exposed": False,
            "source_text_external_upload": False,
        },
    )
