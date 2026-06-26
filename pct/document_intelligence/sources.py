"""Sorgenti reali del fascicolo per l'indicizzazione Lex."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .security import (
    DocumentAIValidationError,
    compute_sha256_bytes,
    sanitize_filename,
    validate_document_file_type,
)

_MIME_BY_EXTENSION = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "txt": "text/plain",
    "xml": "application/xml",
    "json": "application/json",
    "csv": "text/csv",
    "html": "text/html",
    "htm": "text/html",
    "rtf": "application/rtf",
    "odt": "application/vnd.oasis.opendocument.text",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
    "gif": "image/gif",
    "eml": "message/rfc822",
    "msg": "application/vnd.ms-outlook",
    "zip": "application/zip",
    "p7m": "application/pkcs7-mime",
    "pm7": "application/pkcs7-mime",
    "bin": "application/octet-stream",
}


@dataclass(slots=True)
class DocumentAISource:
    tenant_id: str
    fascicolo_id: str
    source_id: str
    source_type: str
    filename: str
    safe_filename: str
    file_type: str
    mime_type: str | None
    size_bytes: int
    sha256: str
    updated_at: str
    relative_path: str = ""
    supported: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    content_bytes: bytes | None = field(default=None, repr=False, compare=False)
    content_path: Path | None = field(default=None, repr=False, compare=False)
    decrypt: Callable[[bytes], bytes] | None = field(default=None, repr=False, compare=False)

    def read_bytes(self) -> bytes:
        if self.content_bytes is not None:
            return bytes(self.content_bytes)
        if self.content_path is None:
            raise DocumentAIValidationError("Contenuto sorgente non disponibile per l'indicizzazione.")
        content = self.content_path.read_bytes()
        if self.decrypt is not None:
            content = self.decrypt(content)
        return bytes(content)

    def public_metadata(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "fascicolo_id": self.fascicolo_id,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "filename": self.filename,
            "file_type": self.file_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "updated_at": self.updated_at,
            "supported": self.supported,
            "metadata": dict(self.metadata),
        }


def source_from_uploaded_document(
    *,
    tenant_id: str,
    fascicolo_id: str,
    document_id: str,
    filename: str,
    content: bytes,
    source_type: str = "documenti_fascicolo",
    mime_type: str | None = None,
    updated_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> DocumentAISource:
    safe_filename = sanitize_filename(filename)
    file_type = validate_document_file_type(safe_filename, mime_type)
    return DocumentAISource(
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        source_id=str(document_id or safe_filename),
        source_type=source_type,
        filename=Path(str(filename)).name,
        safe_filename=safe_filename,
        file_type=file_type,
        mime_type=mime_type or _MIME_BY_EXTENSION.get(file_type),
        size_bytes=len(content),
        sha256=compute_sha256_bytes(content),
        updated_at=updated_at,
        metadata=dict(metadata or {}),
        content_bytes=bytes(content),
    )


def collect_fascicolo_document_sources(
    *,
    tenant_id: str,
    fascicolo_id: str,
    fascicolo: Any,
    documents_root: str | Path,
    decrypt: Callable[[bytes], bytes] | None = None,
) -> list[DocumentAISource]:
    root = Path(documents_root)
    sources: list[DocumentAISource] = []
    for document in list(getattr(fascicolo, "documenti", []) or []):
        source = source_from_fascicolo_document(
            tenant_id=tenant_id,
            fascicolo_id=fascicolo_id,
            document=document,
            documents_root=root,
            decrypt=decrypt,
        )
        if source is not None:
            source.metadata.update(
                _fascicolo_retrieval_metadata(
                    fascicolo,
                    tenant_id=tenant_id,
                    fascicolo_id=fascicolo_id,
                    source_id=source.source_id,
                    sha256=source.sha256,
                    filename=source.filename,
                )
            )
            sources.append(source)
    return sources


def _fascicolo_retrieval_metadata(
    fascicolo: Any,
    *,
    tenant_id: str = "",
    fascicolo_id: str = "",
    source_id: str = "",
    sha256: str = "",
    filename: str = "",
) -> dict[str, str]:
    numero_rg = str(getattr(fascicolo, "numero_rg", "") or "").strip()
    anno_rg = str(getattr(fascicolo, "anno_rg", "") or "").strip()
    rg = f"{numero_rg}/{anno_rg}" if numero_rg and anno_rg and "/" not in numero_rg else numero_rg
    return {
        "tenant_id": str(tenant_id or "").strip(),
        "fascicolo_id": str(fascicolo_id or getattr(fascicolo, "id", "") or "").strip(),
        "document_id": str(source_id or "").strip(),
        "documento": str(filename or "").strip(),
        "sha256": str(sha256 or "").strip(),
        "numero_rg": rg,
        "ufficio": str(getattr(fascicolo, "tribunale", "") or "").strip(),
        "giudice": str(getattr(fascicolo, "giudice", "") or "").strip(),
        "cliente": str(getattr(fascicolo, "nome_cliente", "") or "").strip(),
        "parte_processuale": str(
            getattr(fascicolo, "attore_principale", "") or getattr(fascicolo, "controparte", "") or ""
        ).strip(),
        "oggetto_fascicolo": str(getattr(fascicolo, "oggetto", "") or getattr(fascicolo, "titolo", "") or "").strip(),
    }


def source_from_fascicolo_document(
    *,
    tenant_id: str,
    fascicolo_id: str,
    document: Any,
    documents_root: str | Path,
    decrypt: Callable[[bytes], bytes] | None = None,
) -> DocumentAISource | None:
    filename = Path(str(getattr(document, "nome", "") or "")).name
    if not filename:
        return None
    try:
        safe_filename = sanitize_filename(filename)
    except DocumentAIValidationError:
        safe_filename = filename.replace("\\", "_").replace("/", "_")
        file_type = Path(filename).suffix.lower().lstrip(".")
        supported = False
    else:
        try:
            file_type = validate_document_file_type(safe_filename, None)
        except DocumentAIValidationError:
            file_type = "bin"
            if not safe_filename.lower().endswith(".bin"):
                safe_filename = f"{safe_filename}.bin"
        supported = True

    relative_path = str(getattr(document, "percorso", "") or "").strip()
    content_path = Path(documents_root) / relative_path if relative_path else None
    content: bytes | None = None
    size_bytes = int(getattr(document, "dimensione_bytes", 0) or 0)
    sha256 = str(getattr(document, "hash_sha256", "") or "").strip()
    should_read_content = bool(supported and content_path and content_path.exists() and (not sha256 or decrypt is not None))
    if should_read_content:
        try:
            content = content_path.read_bytes()
            if decrypt is not None:
                content = decrypt(content)
            size_bytes = len(content)
            sha256 = compute_sha256_bytes(content)
        except Exception:
            content = None
    if not sha256 and content:
        sha256 = compute_sha256_bytes(content)

    if supported and filename.lower().endswith((".p7m", ".pm7")) and file_type in _MIME_BY_EXTENSION:
        safe_filename = _safe_inner_p7m_name(safe_filename, file_type)

    fonte = str(getattr(document, "fonte_documento", "") or "").strip()
    source_type = "portale_telematico" if fonte == "PORTALE_TELEMATICO" else "documenti_fascicolo"
    metadata = {
        "documento_id": str(getattr(document, "id", "") or "").strip(),
        "fonte_documento": fonte,
        "tipo_documento": str(getattr(getattr(document, "tipo", None), "value", "") or ""),
        "id_deposito_pct": str(getattr(document, "id_deposito_pct", "") or "").strip(),
        "nome_portale": str(getattr(document, "nome_portale", "") or "").strip(),
        "classificazione_portale": str(getattr(document, "classificazione_portale", "") or "").strip(),
    }
    return DocumentAISource(
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        source_id=str(getattr(document, "id", "") or filename),
        source_type=source_type,
        filename=filename,
        safe_filename=safe_filename,
        file_type=file_type,
        mime_type=_MIME_BY_EXTENSION.get(file_type),
        size_bytes=size_bytes,
        sha256=sha256,
        updated_at=str(getattr(document, "data_caricamento", "") or getattr(document, "data_documento", "") or ""),
        relative_path=relative_path,
        supported=supported,
        metadata=metadata,
        content_path=content_path if content is None else None,
        content_bytes=content,
        decrypt=decrypt if content is None else None,
    )


def _safe_inner_p7m_name(safe_filename: str, file_type: str) -> str:
    name = str(safe_filename or "").strip()
    if name.lower().endswith((".p7m", ".pm7")):
        name = name[:-4]
    if not name.lower().endswith(f".{file_type}"):
        name = f"{name}.{file_type}"
    return name


__all__ = [
    "DocumentAISource",
    "collect_fascicolo_document_sources",
    "source_from_fascicolo_document",
    "source_from_uploaded_document",
]
