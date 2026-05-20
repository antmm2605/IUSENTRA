"""Registro evidenze procedurali con hash e collegamenti a firma, deposito e notifica."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_evidence_document(
    repo: ProcedureLifecycleRepository,
    *,
    fascicolo_id: str,
    evidence_type: str,
    document_id: str,
    storage_path: str = "",
    **payload: Any,
) -> int:
    file_hash = payload.get("hash")
    if storage_path and not file_hash:
        path = Path(storage_path)
        if path.exists() and path.is_file():
            file_hash = _sha256_file(path)
    return repo.add_evidence_document(
        {
            "fascicolo_id": fascicolo_id,
            "evidence_type": evidence_type,
            "document_id": document_id,
            "source_event_id": payload.get("source_event_id"),
            "hash": file_hash,
            "filename_original": payload.get("filename_original"),
            "storage_path": storage_path or None,
            "legal_relevance": payload.get("legal_relevance"),
            "retention_policy": payload.get("retention_policy"),
            "notes": payload.get("notes"),
        }
    )


def list_evidence_for_fascicolo(repo: ProcedureLifecycleRepository, fascicolo_id: str) -> list[dict[str, Any]]:
    return repo.list_evidence_documents(fascicolo_id)


def assert_required_evidence(
    repo: ProcedureLifecycleRepository,
    fascicolo_id: str,
    required_evidence_types: list[str] | tuple[str, ...],
) -> None:
    existing = {
        str(row.get("evidence_type") or "")
        for row in repo.list_evidence_documents(fascicolo_id)
    }
    missing = [item for item in required_evidence_types if item not in existing]
    if missing:
        raise ValueError(f"Evidenze mancanti: {', '.join(missing)}")


def link_evidence_to_notification(
    repo: ProcedureLifecycleRepository,
    *,
    notification_id: int,
    evidence_id: int,
) -> None:
    notification = repo.get_notification_event(notification_id)
    if not notification:
        raise ValueError("Notifica non trovata.")
    with repo.connect() as conn:
        evidence = repo._fetch_one(conn, "SELECT * FROM evidence_documents WHERE id = ?", (evidence_id,))
    if not evidence:
        raise ValueError("Evidenza non trovata.")
    repo.update_notification_event(
        notification_id,
        {
            "proof_bundle_id": str(evidence.get("document_id") or evidence_id),
            "status": "PROOF_ACQUIRED",
        },
        source="notification_proof_validation",
    )


def link_evidence_to_deposit(
    repo: ProcedureLifecycleRepository,
    *,
    package_id: int,
    evidence_id: int,
) -> None:
    package = repo.get_deposit_package(package_id)
    if not package:
        raise ValueError("Pacchetto deposito non trovato.")
    with repo.connect() as conn:
        evidence = repo._fetch_one(conn, "SELECT * FROM evidence_documents WHERE id = ?", (evidence_id,))
    if not evidence:
        raise ValueError("Evidenza non trovata.")
    repo.update_deposit_package(
        package_id,
        {
            "notes": f"Evidenza collegata: {evidence.get('document_id') or evidence_id}",
        },
    )
