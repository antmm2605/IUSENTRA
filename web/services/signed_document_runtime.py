from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pct.firme_cades import (
    SignedDocumentPayload,
    SignedDocumentStatus,
    inspect_signed_document_bytes,
    is_p7m_filename,
)


def _nome_preview_documento(nome_file: str) -> str:
    nome = Path(str(nome_file or "")).name.strip()
    return nome[:-4] if nome.lower().endswith(".p7m") else nome


def _tipo_contenuto_label(status: SignedDocumentStatus) -> str:
    mapping = {
        "application/pdf": "PDF",
        "application/xml": "XML",
        "text/xml": "XML",
        "application/json": "JSON",
        "text/plain": "Testo",
        "text/html": "HTML",
        "application/zip": "Archivio ZIP",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    }
    return mapping.get(str(status.payload_mime or "").strip().lower(), "Sconosciuto")


def build_signed_document_ui_status(status: SignedDocumentStatus | None) -> dict[str, Any] | None:
    if status is None or not status.is_signed_container:
        return None

    if status.payload_available:
        content_label = "Contenuto estratto"
        tone = "success"
    else:
        content_label = "Contenuto non disponibile"
        tone = "warning"

    signature_label = "Firma verificata" if status.signature_verified else "Firma da verificare"
    internal_label = _tipo_contenuto_label(status)
    actions: list[str] = ["Verifica firma"]
    if status.payload_available:
        actions.extend(["Apri file interno", "Invia ad AI"])
    else:
        actions.append("Segnala file originale mancante")

    return {
        "is_signed_container": True,
        "content_available": bool(status.payload_available),
        "content_label": content_label,
        "signature_label": signature_label,
        "internal_content_label": internal_label,
        "tone": tone,
        "message": status.message,
        "embedded_payload": bool(status.embedded_payload),
        "detached_signature": bool(status.detached_signature),
        "payload_available": bool(status.payload_available),
        "payload_mime": status.payload_mime,
        "payload_name": status.payload_name,
        "actions": actions,
    }


def build_document_version_candidates(
    gestore_fascicoli: Any,
    documento: Any,
    *,
    decrypt_doc: Callable[[bytes], bytes],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    docs_dir = Path(getattr(gestore_fascicoli, "documents_dir", ""))
    for versione in reversed(list(getattr(documento, "versioni", []) or [])):
        percorso_rel = str(getattr(versione, "percorso", "") or "").strip()
        if not percorso_rel:
            continue
        percorso = docs_dir / percorso_rel
        if not percorso.exists():
            continue
        if Path(percorso_rel).name.lower().endswith(".p7m"):
            continue
        try:
            payload = decrypt_doc(percorso.read_bytes())
        except Exception:
            continue
        candidates.append(
            {
                "name": Path(percorso_rel).name,
                "path": str(percorso),
                "payload": payload,
            }
        )
    return candidates


def prepare_signed_document_for_reading(
    *,
    source_name: str,
    data: bytes,
    version_candidates: list[dict[str, Any]] | None = None,
    source_path: str = "",
) -> SignedDocumentPayload:
    primary = inspect_signed_document_bytes(
        source_name=source_name,
        source_path=source_path,
        data=data,
    )
    if primary.status.payload_available:
        return primary

    for candidate in version_candidates or []:
        prepared = inspect_signed_document_bytes(
            source_name=source_name,
            source_path=source_path,
            data=data,
            original_detached_bytes=candidate.get("payload"),
            original_detached_name=str(candidate.get("name") or "").strip() or None,
        )
        if prepared.status.payload_available:
            return prepared

    return primary


def build_document_signed_snapshot_from_bytes(
    *,
    source_name: str,
    data: bytes,
    version_candidates: list[dict[str, Any]] | None = None,
    source_path: str = "",
) -> dict[str, Any] | None:
    if not is_p7m_filename(source_name):
        return None
    prepared = prepare_signed_document_for_reading(
        source_name=source_name,
        source_path=source_path,
        data=data,
        version_candidates=version_candidates,
    )
    return {
        "signed_status": prepared.status.to_dict(),
        "ui_status": build_signed_document_ui_status(prepared.status),
        "preview_name": _nome_preview_documento(source_name),
    }


__all__ = [
    "build_document_signed_snapshot_from_bytes",
    "build_document_version_candidates",
    "build_signed_document_ui_status",
    "prepare_signed_document_for_reading",
]
