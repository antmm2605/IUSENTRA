"""Rilevamento MIME deterministico senza dipendenze native obbligatorie."""

from __future__ import annotations

import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".doc",
    ".docx",
    ".xml",
    ".p7m",
    ".eml",
    ".msg",
    ".zip",
    ".txt",
    ".csv",
    ".json",
}

EXTENSION_BY_MIME = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
    "application/zip": ".zip",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "application/pkcs7-mime": ".p7m",
    "application/x-pkcs7-mime": ".p7m",
    "message/rfc822": ".eml",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/json": ".json",
}


@dataclass(slots=True)
class MimeDetection:
    mime_type: str
    extension: str
    confidence: float
    source: str
    supported: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "mime_type": self.mime_type,
            "extension": self.extension,
            "confidence": self.confidence,
            "source": self.source,
            "supported": self.supported,
            "warnings": list(self.warnings),
        }


def detect_mime(data: bytes, filename: str = "", *, allowed_extensions: Iterable[str] | None = None) -> MimeDetection:
    """Detect MIME from magic bytes first, then extension as a compatibility hint."""

    raw = bytes(data or b"")
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix == ".p7m":
        inner_suffix = Path(str(filename or "")[:-4]).suffix.lower()
        suffix = ".p7m" if not inner_suffix else f"{inner_suffix}.p7m"
    mime = ""
    ext = ""
    source = "magic"
    confidence = 0.98
    warnings: list[str] = []
    stripped = raw[:4096].lstrip()

    if stripped.startswith(b"%PDF"):
        mime, ext = "application/pdf", ".pdf"
    elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
        mime, ext = "image/png", ".png"
    elif raw.startswith(b"\xff\xd8\xff"):
        mime, ext = "image/jpeg", ".jpg"
    elif raw.startswith((b"II*\x00", b"MM\x00*")):
        mime, ext = "image/tiff", ".tiff"
    elif raw.startswith(b"PK\x03\x04") or raw.startswith(b"PK\x05\x06") or raw.startswith(b"PK\x07\x08"):
        if _looks_like_docx(raw):
            mime, ext = "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx"
        else:
            mime, ext = "application/zip", ".zip"
    elif raw.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        mime, ext = "application/msword", ".doc"
    elif stripped.startswith((b"<?xml", b"<postacert", b"<dati", b"<ns")):
        mime, ext = "application/xml", ".xml"
    elif _looks_like_email(raw):
        mime, ext = "message/rfc822", ".eml"
    elif suffix.endswith(".p7m") or raw.startswith((b"-----BEGIN PKCS7", b"-----BEGIN CMS", b"\x30\x82")):
        mime, ext = "application/pkcs7-mime", ".p7m"
    elif _looks_like_text(raw):
        mime, ext = _text_mime_from_extension(suffix)
        confidence = 0.82
    else:
        guessed, _encoding = mimetypes.guess_type(str(filename or ""))
        mime = guessed or "application/octet-stream"
        ext = suffix if suffix and suffix in SUPPORTED_EXTENSIONS else EXTENSION_BY_MIME.get(mime, suffix or "")
        source = "extension" if guessed or suffix else "unknown"
        confidence = 0.55 if source == "extension" else 0.2
        if source == "unknown":
            warnings.append("Formato non riconosciuto dai byte iniziali.")

    if not ext:
        ext = EXTENSION_BY_MIME.get(mime, suffix or "")
    if suffix and ext and suffix not in {ext, ".p7m"} and not suffix.endswith(".p7m"):
        warnings.append("Estensione dichiarata diversa dal formato rilevato.")

    allowed = {str(item).lower() for item in (allowed_extensions or SUPPORTED_EXTENSIONS)}
    supported = ext.lower() in allowed or any(str(ext).lower().endswith(item) for item in allowed if item == ".p7m")
    if not supported:
        warnings.append("Formato non ammesso dalla configurazione.")
    return MimeDetection(mime, ext.lower(), round(confidence, 3), source, supported, warnings)


def normalized_extension(filename: str, mime_type: str = "") -> str:
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix:
        return suffix
    return EXTENSION_BY_MIME.get(str(mime_type or "").lower(), "")


def _looks_like_docx(raw: bytes) -> bool:
    sample = raw[:200000]
    return b"[Content_Types].xml" in sample and b"word/" in sample


def _looks_like_email(raw: bytes) -> bool:
    sample = raw[:4096].decode("utf-8", errors="ignore").lower()
    return ("from:" in sample and "subject:" in sample) or ("message-id:" in sample and "mime-version:" in sample)


def _looks_like_text(raw: bytes) -> bool:
    if not raw:
        return False
    sample = raw[:4096]
    if b"\x00" in sample:
        return False
    decoded = sample.decode("utf-8", errors="ignore")
    if not decoded:
        return False
    printable = sum(1 for char in decoded if char.isprintable() or char.isspace())
    return printable / max(len(decoded), 1) > 0.82


def _text_mime_from_extension(suffix: str) -> tuple[str, str]:
    if suffix == ".csv":
        return "text/csv", ".csv"
    if suffix == ".json":
        return "application/json", ".json"
    if suffix == ".xml":
        return "application/xml", ".xml"
    return "text/plain", ".txt"
