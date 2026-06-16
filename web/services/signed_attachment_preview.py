"""Anteprima comune per allegati e documenti firmati CAdES."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass

from pct.firme_cades import (
    inner_signed_name,
    inspect_signed_document_bytes,
    is_p7m_filename,
    payload_mime_from_bytes,
)


INLINE_PREVIEW_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "text/plain",
    "text/html",
    "application/xml",
    "text/xml",
}


@dataclass(slots=True)
class AttachmentPreviewPayload:
    data: bytes
    mimetype: str
    download_name: str
    extracted_from_signature: bool = False
    unavailable_reason: str = ""


def attachment_mimetype(nome_file: str, mime_salvato: str = "") -> str:
    saved = str(mime_salvato or "").strip()
    guessed = mimetypes.guess_type(str(nome_file or ""))[0] or ""
    if saved in {"", "application/octet-stream", "binary/octet-stream"} and guessed:
        return guessed
    return saved or guessed or "application/octet-stream"


def is_inline_preview_mime(mimetype: str) -> bool:
    mime = str(mimetype or "").split(";", 1)[0].strip().lower()
    return mime in INLINE_PREVIEW_MIME_TYPES


def build_attachment_preview_payload(
    *,
    nome_file: str,
    data: bytes,
    mime_salvato: str = "",
) -> AttachmentPreviewPayload:
    """Prepara il contenuto da mostrare inline.

    Per un file .pdf.p7m l'originale resta invariato per il download, ma
    l'anteprima usa il PDF interno quando il contenitore CAdES lo espone.
    """

    original_name = str(nome_file or "").strip() or "allegato"
    original_mime = attachment_mimetype(original_name, mime_salvato)
    if not is_p7m_filename(original_name):
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=original_name,
        )

    signed = inspect_signed_document_bytes(
        source_name=original_name,
        source_path="",
        data=data,
    )
    if signed.status.payload_available and signed.payload_bytes:
        preview_name = signed.status.payload_name or inner_signed_name(original_name)
        preview_mime = signed.status.payload_mime or payload_mime_from_bytes(signed.payload_bytes, preview_name)
        if is_inline_preview_mime(preview_mime):
            return AttachmentPreviewPayload(
                data=signed.payload_bytes,
                mimetype=preview_mime,
                download_name=preview_name,
                extracted_from_signature=True,
            )
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=original_name,
            unavailable_reason=(
                "Il file firmato è stato letto, ma il contenuto interno non è "
                "un formato visualizzabile direttamente nel browser."
            ),
        )

    return AttachmentPreviewPayload(
        data=data,
        mimetype=original_mime,
        download_name=original_name,
        unavailable_reason=(
            "Il file firmato non espone un PDF interno leggibile. Scarica il .p7m "
            "originale e verificalo con il software di firma."
        ),
    )
