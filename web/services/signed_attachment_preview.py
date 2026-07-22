"""Anteprima comune e governata per documenti, archivi e firme digitali."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import io
import mimetypes
from pathlib import PurePosixPath
import zipfile

from pct.firme_cades import (
    inner_signed_name,
    inspect_signed_document_bytes,
    is_signed_container,
    payload_mime_from_bytes,
)


INLINE_PREVIEW_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/tiff",
    "text/plain",
    "text/html",
    "application/xml",
    "text/xml",
    "message/rfc822",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_ARCHIVE_FILES = 128
MAX_ARCHIVE_MEMBER_BYTES = 40 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 120 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 250
MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES = 4 * 1024 * 1024
ARCHIVE_LEGAL_KEYWORDS = (
    "udienza",
    "decreto",
    "ordinanza",
    "provvedimento",
    "verbale",
    "fissazione",
    "sentenza",
)


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


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "iso-8859-1", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
        except LookupError:
            continue
    return data.decode("utf-8", errors="replace")


def _textual_unavailable(
    *,
    nome_file: str,
    data: bytes,
    mimetype: str,
    signed: bool,
    reason: str,
) -> AttachmentPreviewPayload:
    return AttachmentPreviewPayload(
        data=data,
        mimetype=mimetype,
        download_name=nome_file,
        extracted_from_signature=signed,
        unavailable_reason=reason,
    )


def _preview_shell(*, title: str, subtitle: str, body: str) -> bytes:
    html = (
        '<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<style>"
        ":root{color-scheme:light;--ink:#172033;--muted:#5d6b82;--line:#dfe6ef;--soft:#f6f8fb;--brand:#1458d4}"
        "*{box-sizing:border-box}body{margin:0;background:var(--soft);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif}"
        ".wrap{max-width:1040px;margin:24px auto;padding:0 18px}"
        ".head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}"
        ".eyebrow{font-size:12px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;color:var(--brand);margin-bottom:4px}"
        "h1{font-size:22px;line-height:1.25;margin:0 0 4px;font-weight:800}p{line-height:1.55}"
        ".subtitle{color:var(--muted);font-size:14px;margin:0}.card{background:#fefefe;border:1px solid var(--line);border-radius:8px;padding:22px;box-shadow:0 8px 22px rgba(23,50,77,.08)}"
        "dl{display:grid;grid-template-columns:minmax(120px,170px) 1fr;gap:8px 16px;margin:0 0 18px}"
        "dt{font-weight:700;color:#42526b}dd{margin:0;word-break:break-word}"
        "pre{margin:0;white-space:pre-wrap;word-break:break-word;font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,'Liberation Mono',monospace;color:#111827}"
        ".body p{margin:0 0 12px}.body p:last-child{margin-bottom:0}ul{margin:0;padding-left:20px}.muted{color:var(--muted);font-size:13px}"
        ".word-doc{font-family:Georgia,'Times New Roman',serif;font-size:16px;line-height:1.65;color:#111827}.word-doc p{margin:0 0 12px}.word-doc table{width:100%;border-collapse:collapse;margin:14px 0}.word-doc td,.word-doc th{border:1px solid #d7dde8;padding:8px;vertical-align:top}.image-reader{display:grid;gap:18px}.image-reader figure{margin:0;display:grid;gap:8px}.image-reader img{max-width:100%;height:auto;border:1px solid #d7dde8;border-radius:10px;background:#fff;box-shadow:0 10px 24px rgba(15,23,42,.08)}"
        "@media(max-width:700px){.wrap{margin:12px auto;padding:0 12px}.card{padding:16px}dl{grid-template-columns:1fr;gap:4px}h1{font-size:19px}}"
        "</style></head><body><main class=\"wrap\">"
        '<header class="head"><div>'
        f'<div class="eyebrow">{escape(subtitle)}</div>'
        f"<h1>{escape(title)}</h1>"
        "</div></header>"
        f'<section class="card">{body}</section>'
        "</main></body></html>"
    )
    return html.encode("utf-8")


def _zip_declared_directory(data: bytes) -> tuple[int, int, int] | None:
    """Valida la directory centrale ZIP senza costruire l'elenco dei membri."""

    search_start = max(0, len(data) - (65_535 + 22))
    eocd_offset = data.rfind(b"PK\x05\x06", search_start)
    if eocd_offset < 0 or eocd_offset + 22 > len(data):
        return None
    entries = int.from_bytes(data[eocd_offset + 10 : eocd_offset + 12], "little")
    central_size = int.from_bytes(data[eocd_offset + 12 : eocd_offset + 16], "little")
    central_offset = int.from_bytes(data[eocd_offset + 16 : eocd_offset + 20], "little")
    if entries == 0xFFFF or central_size == 0xFFFFFFFF or central_offset == 0xFFFFFFFF:
        return None
    central_end = central_offset + central_size
    if central_end > eocd_offset:
        return None

    cursor = central_offset
    parsed_entries = 0
    while cursor < central_end:
        if cursor + 46 > central_end or data[cursor : cursor + 4] != b"PK\x01\x02":
            return None
        filename_length = int.from_bytes(data[cursor + 28 : cursor + 30], "little")
        extra_length = int.from_bytes(data[cursor + 30 : cursor + 32], "little")
        comment_length = int.from_bytes(data[cursor + 32 : cursor + 34], "little")
        cursor += 46 + filename_length + extra_length + comment_length
        parsed_entries += 1
        if parsed_entries > entries:
            return None
    if cursor != central_end or parsed_entries != entries:
        return None
    return entries, central_size, central_offset


def _render_supported_textual_preview(
    *,
    nome_file: str,
    data: bytes,
    mimetype: str,
    signed: bool,
) -> AttachmentPreviewPayload | None:
    from web.services.signed_attachment_preview_images import render_image_preview
    from web.services.signed_attachment_preview_text import (
        render_eml_preview,
        render_html_preview,
        render_text_preview,
        render_xml_preview,
    )
    from web.services.signed_attachment_preview_word import render_doc_preview, render_docx_preview

    lower = str(nome_file or "").lower()
    mime = str(mimetype or "").split(";", 1)[0].strip().lower()
    sample = data.lstrip()[:80]
    if lower.endswith(".eml") or mime == "message/rfc822":
        return render_eml_preview(nome_file, data, signed=signed)
    if lower.endswith(".xml") or mime in {"application/xml", "text/xml"} or sample.startswith(
        (b"<?xml", b"<DatiAtto", b"<Segnatura")
    ):
        return render_xml_preview(nome_file, data, signed=signed)
    if lower.endswith(".txt") or mime == "text/plain":
        return render_text_preview(nome_file, data, signed=signed)
    if lower.endswith((".html", ".htm")) or mime == "text/html":
        return render_html_preview(nome_file, data, signed=signed)
    if lower.endswith(".docx") or mime == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ):
        return render_docx_preview(nome_file, data, signed=signed)
    if lower.endswith(".doc") or mime == "application/msword":
        return render_doc_preview(nome_file, data, signed=signed)
    if lower.endswith((".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff")) or mime in {
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/tiff",
    }:
        return render_image_preview(nome_file, data, mimetype=mime, signed=signed)
    return None


def _archive_member_priority(info: zipfile.ZipInfo) -> tuple[int, int, str]:
    lower = info.filename.casefold()
    if lower.endswith(".pdf"):
        format_rank = 0
    elif lower.endswith((".pdf.p7m", ".p7m", ".p7s")):
        format_rank = 1
    elif lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".tif", ".tiff")):
        format_rank = 2
    elif lower.endswith((".eml", ".xml", ".txt")):
        format_rank = 3
    elif lower.endswith((".docx", ".doc", ".html", ".htm")):
        format_rank = 4
    else:
        format_rank = 9
    semantic_rank = 0 if any(keyword in lower for keyword in ARCHIVE_LEGAL_KEYWORDS) else 1
    return format_rank, semantic_rank, lower


def _archive_preview_payload(
    *,
    nome_file: str,
    data: bytes,
    archive_depth: int,
) -> AttachmentPreviewPayload:
    original_mime = attachment_mimetype(nome_file, "application/zip")
    if archive_depth > 0:
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=nome_file,
            unavailable_reason="L'archivio contiene un ulteriore archivio: scarica l'originale per verificarlo.",
        )

    try:
        archive_stream = io.BytesIO(data)
        if not zipfile.is_zipfile(archive_stream):
            raise zipfile.BadZipFile
        declared = _zip_declared_directory(data)
        if declared is None:
            raise ValueError("L'archivio ZIP non contiene una struttura valida.")
        declared_entries, central_size, _central_offset = declared
        if declared_entries > MAX_ARCHIVE_FILES:
            raise ValueError("L'archivio ZIP contiene troppi file per una visualizzazione sicura.")
        if central_size > MAX_ARCHIVE_CENTRAL_DIRECTORY_BYTES:
            raise ValueError("La struttura dell'archivio ZIP supera il limite di sicurezza previsto.")
        archive_stream.seek(0)
        with zipfile.ZipFile(archive_stream, "r") as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if not members:
                raise ValueError("L'archivio ZIP non contiene documenti.")
            if len(members) > MAX_ARCHIVE_FILES:
                raise ValueError("L'archivio ZIP contiene troppi file per una visualizzazione sicura.")

            total_size = 0
            candidates: list[zipfile.ZipInfo] = []
            for info in members:
                member_name = info.filename.replace("\\", "/")
                member_path = PurePosixPath(member_name)
                if (
                    not member_name
                    or member_name.startswith("/")
                    or ".." in member_path.parts
                    or (member_path.parts and ":" in member_path.parts[0])
                ):
                    raise ValueError("L'archivio ZIP contiene un percorso non sicuro.")
                unix_mode = (info.external_attr >> 16) & 0o170000
                if unix_mode == 0o120000:
                    raise ValueError("L'archivio ZIP contiene un collegamento non sicuro.")
                if info.flag_bits & 0x1:
                    raise ValueError(
                        "L'archivio ZIP contiene file cifrati e non può essere aperto automaticamente."
                    )
                if info.file_size > MAX_ARCHIVE_MEMBER_BYTES:
                    raise ValueError("Un documento nell'archivio ZIP supera il limite di visualizzazione.")
                total_size += info.file_size
                if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                    raise ValueError("L'archivio ZIP supera il limite complessivo di visualizzazione.")
                if info.file_size and (
                    not info.compress_size
                    or info.file_size / info.compress_size > MAX_ARCHIVE_COMPRESSION_RATIO
                ):
                    raise ValueError(
                        "L'archivio ZIP presenta una compressione anomala e non viene aperto automaticamente."
                    )
                if _archive_member_priority(info)[0] < 9:
                    candidates.append(info)

            for info in sorted(candidates, key=_archive_member_priority):
                member_data = archive.read(info)
                member_name = PurePosixPath(info.filename.replace("\\", "/")).name
                preview = build_attachment_preview_payload(
                    nome_file=member_name,
                    data=member_data,
                    mime_salvato=attachment_mimetype(member_name),
                    _archive_depth=archive_depth + 1,
                )
                if not preview.unavailable_reason and is_inline_preview_mime(preview.mimetype):
                    return preview
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=nome_file,
            unavailable_reason=str(exc) or "L'archivio ZIP non è leggibile.",
        )

    return AttachmentPreviewPayload(
        data=data,
        mimetype=original_mime,
        download_name=nome_file,
        unavailable_reason="L'archivio ZIP non contiene documenti visualizzabili direttamente.",
    )


def build_attachment_preview_payload(
    *,
    nome_file: str,
    data: bytes,
    mime_salvato: str = "",
    _archive_depth: int = 0,
) -> AttachmentPreviewPayload:
    """Prepara il contenuto interno, mantenendo invariato l'originale per il download."""

    original_name = str(nome_file or "").strip() or "allegato"
    original_mime = attachment_mimetype(original_name, mime_salvato)
    if original_name.casefold().endswith(".zip") or original_mime in {
        "application/zip",
        "application/x-zip-compressed",
    }:
        return _archive_preview_payload(
            nome_file=original_name,
            data=data,
            archive_depth=_archive_depth,
        )
    if not is_signed_container(original_name, original_mime):
        textual = _render_supported_textual_preview(
            nome_file=original_name,
            data=data,
            mimetype=original_mime,
            signed=False,
        )
        if textual:
            return textual
        return AttachmentPreviewPayload(
            data=data,
            mimetype=original_mime,
            download_name=original_name,
        )

    signed = inspect_signed_document_bytes(
        source_name=original_name,
        source_path="",
        source_mime=original_mime,
        data=data,
    )
    if signed.status.payload_available and signed.payload_bytes:
        preview_name = signed.status.payload_name or inner_signed_name(original_name)
        preview_mime = signed.status.payload_mime or payload_mime_from_bytes(
            signed.payload_bytes,
            preview_name,
        )
        textual = _render_supported_textual_preview(
            nome_file=preview_name,
            data=signed.payload_bytes,
            mimetype=preview_mime,
            signed=True,
        )
        if textual:
            return textual
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
            "Il contenitore firmato non espone un contenuto interno leggibile. "
            "Scarica l'originale e verificalo con il software di firma."
        ),
    )


__all__ = [
    "AttachmentPreviewPayload",
    "attachment_mimetype",
    "build_attachment_preview_payload",
    "is_inline_preview_mime",
]
