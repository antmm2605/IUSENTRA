"""Validazione upload per estensione, MIME, magic bytes e path traversal."""

from __future__ import annotations

import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UploadValidationResult:
    ok: bool
    safe_filename: str = ""
    mime_type: str = ""
    error: str = ""


_DANGEROUS_DOUBLE_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".js", ".vbs", ".scr"}


def validate_upload(
    filename: str,
    content: bytes,
    *,
    allowed_extensions: tuple[str, ...],
    allowed_mime_types: tuple[str, ...],
    max_size_mb: int,
) -> UploadValidationResult:
    safe_name = sanitize_filename(filename)
    if not safe_name:
        return UploadValidationResult(False, error="Nome file non valido")
    if Path(filename).name != filename or ".." in Path(filename).parts:
        return UploadValidationResult(False, error="Percorso file non consentito")
    if not content:
        return UploadValidationResult(False, error="File vuoto")
    if len(content) > max(1, int(max_size_mb)) * 1024 * 1024:
        return UploadValidationResult(False, error="File troppo grande")
    suffixes = [suffix.lower() for suffix in Path(safe_name).suffixes]
    ext = suffixes[-1] if suffixes else ""
    if ext not in {item.lower() for item in allowed_extensions}:
        return UploadValidationResult(False, error="Estensione non consentita")
    if any(suffix in _DANGEROUS_DOUBLE_EXTENSIONS for suffix in suffixes[:-1]):
        return UploadValidationResult(False, error="Doppia estensione pericolosa")
    mime_type = detect_mime_type(safe_name, content)
    if allowed_mime_types and mime_type not in set(allowed_mime_types):
        return UploadValidationResult(False, safe_filename=safe_name, mime_type=mime_type, error="MIME non consentito")
    if ext == ".pdf" and not content.startswith(b"%PDF"):
        return UploadValidationResult(False, safe_filename=safe_name, mime_type=mime_type, error="PDF non valido")
    if ext in {".xml"} and (b"<!ENTITY" in content[:4096].upper() or b"<!DOCTYPE" in content[:4096].upper()):
        return UploadValidationResult(
            False,
            safe_filename=safe_name,
            mime_type=mime_type,
            error="XML con entita' esterne non consentito",
        )
    return UploadValidationResult(True, safe_filename=safe_name, mime_type=mime_type)


def sanitize_filename(filename: str) -> str:
    name = Path(str(filename or "")).name.strip()
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name)
    return name[:180].strip(" .")


def detect_mime_type(filename: str, content: bytes) -> str:
    head = content[:16]
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"PK\x03\x04"):
        return "application/zip"
    if head.startswith(b"\x89PNG"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.lstrip().startswith(b"<"):
        return "application/xml"
    if Path(filename).suffix.lower() in {".p7m", ".p7s"}:
        return "application/pkcs7-mime"
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"
