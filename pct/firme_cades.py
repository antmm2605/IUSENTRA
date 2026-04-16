from __future__ import annotations

import io
import mimetypes
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path


@dataclass(slots=True)
class SignedDocumentStatus:
    source_path: str
    source_name: str
    is_signed_container: bool
    signature_format: str
    openssl_available: bool

    extraction_attempted: bool
    extraction_ok: bool
    embedded_payload: bool
    detached_signature: bool

    signature_verified: bool
    chain_verified: bool

    payload_available: bool
    payload_path: str | None
    payload_name: str | None
    payload_extension: str | None
    payload_mime: str | None
    payload_size: int | None

    message: str
    technical_details: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class SignedDocumentPayload:
    status: SignedDocumentStatus
    payload_bytes: bytes | None = None


def is_p7m_filename(path: str | Path) -> bool:
    return str(path or "").strip().lower().endswith(".p7m")


def inner_signed_path(path: str | Path) -> Path:
    file_path = Path(path)
    return file_path.with_suffix("") if is_p7m_filename(file_path.name) else file_path


def inner_signed_name(name: str) -> str:
    text = str(name or "").strip()
    return text[:-4] if text.lower().endswith(".p7m") else text


def payload_mime_from_bytes(data: bytes, original_name: str = "") -> str:
    sample = bytes(data[:32] if data else b"")
    lower_name = str(original_name or "").strip().lower()
    if sample.startswith(b"%PDF"):
        return "application/pdf"
    if sample.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                names = set(archive.namelist())
            if "word/document.xml" in names or lower_name.endswith(".docx"):
                return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        except Exception:
            pass
        return "application/zip"
    if sample.lstrip().startswith(b"{") or sample.lstrip().startswith(b"["):
        return "application/json"
    if sample.lstrip().startswith(b"<?xml") or sample.lstrip().startswith(b"<"):
        return "application/xml"
    guessed, _ = mimetypes.guess_type(original_name or "")
    if guessed:
        return guessed
    return "text/plain"


def payload_extension_from_mime(mime_type: str, source_name: str = "") -> str | None:
    lower_name = str(source_name or "").strip().lower()
    mapping = {
        "application/pdf": ".pdf",
        "application/xml": ".xml",
        "text/xml": ".xml",
        "application/json": ".json",
        "text/plain": ".txt",
        "text/markdown": ".md",
        "text/html": ".html",
        "application/zip": ".zip",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    if lower_name.endswith(".docx.p7m") or lower_name.endswith(".docx"):
        return ".docx"
    return mapping.get(str(mime_type or "").strip().lower(), None)


def payload_name_from_source(source_name: str, payload_ext: str | None = None) -> str:
    base = inner_signed_name(source_name)
    if payload_ext and not base.lower().endswith(payload_ext.lower()):
        base = f"{base}{payload_ext}"
    return base


def extract_signed_payload(data: bytes) -> bytes | None:
    try:
        from asn1crypto import cms
    except Exception:
        return None

    try:
        content_info = cms.ContentInfo.load(data)
        if content_info["content_type"].native != "signed_data":
            return None
        signed_data = content_info["content"]
        encap = signed_data["encap_content_info"]
        content = encap["content"]
        if content is None:
            return None
        native = getattr(content, "native", None)
        if isinstance(native, bytes):
            return native
        if isinstance(content, bytes):
            return content
        if native is not None:
            try:
                return bytes(native)
            except Exception:
                return None
    except Exception:
        return None
    return None


def _run_command(cmd: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:
        return False, str(exc)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    details = stderr or stdout or f"returncode={result.returncode}"
    return result.returncode == 0, details


@lru_cache(maxsize=1)
def _openssl_available() -> bool:
    ok, _ = _run_command(["openssl", "version"])
    return ok


def _extract_with_openssl_smime(p7m_path: Path, output_path: Path) -> tuple[bool, str]:
    return _run_command(
        [
            "openssl",
            "smime",
            "-verify",
            "-inform",
            "DER",
            "-in",
            str(p7m_path),
            "-noverify",
            "-out",
            str(output_path),
        ]
    )


def _extract_with_openssl_cms(p7m_path: Path, output_path: Path) -> tuple[bool, str]:
    return _run_command(
        [
            "openssl",
            "cms",
            "-verify",
            "-binary",
            "-inform",
            "DER",
            "-in",
            str(p7m_path),
            "-noverify",
            "-out",
            str(output_path),
        ]
    )


def _verify_detached_with_openssl_smime(p7m_path: Path, content_path: Path, output_path: Path) -> tuple[bool, str]:
    return _run_command(
        [
            "openssl",
            "smime",
            "-verify",
            "-inform",
            "DER",
            "-in",
            str(p7m_path),
            "-content",
            str(content_path),
            "-noverify",
            "-out",
            str(output_path),
        ]
    )


def _verify_detached_with_openssl_cms(p7m_path: Path, content_path: Path, output_path: Path) -> tuple[bool, str]:
    return _run_command(
        [
            "openssl",
            "cms",
            "-verify",
            "-binary",
            "-inform",
            "DER",
            "-in",
            str(p7m_path),
            "-content",
            str(content_path),
            "-noverify",
            "-out",
            str(output_path),
        ]
    )


def inspect_signed_document_bytes(
    *,
    source_name: str,
    data: bytes,
    source_path: str = "",
    original_detached_bytes: bytes | None = None,
    original_detached_name: str | None = None,
) -> SignedDocumentPayload:
    openssl_ok = _openssl_available()
    base_status = SignedDocumentStatus(
        source_path=str(source_path or ""),
        source_name=str(source_name or ""),
        is_signed_container=is_p7m_filename(source_name),
        signature_format="cades" if is_p7m_filename(source_name) else "unknown",
        openssl_available=openssl_ok,
        extraction_attempted=is_p7m_filename(source_name),
        extraction_ok=False,
        embedded_payload=False,
        detached_signature=False,
        signature_verified=False,
        chain_verified=False,
        payload_available=False,
        payload_path=None,
        payload_name=None,
        payload_extension=None,
        payload_mime=None,
        payload_size=None,
        message="Il file non ha estensione .p7m",
    )
    if not base_status.is_signed_container:
        return SignedDocumentPayload(status=base_status, payload_bytes=None)

    details = ""
    payload_bytes: bytes | None = None
    signature_verified = False
    embedded_payload = False
    detached_signature = False

    if openssl_ok:
        try:
            with tempfile.TemporaryDirectory(prefix="iusentra-p7m-") as tmp:
                tmp_dir = Path(tmp)
                p7m_path = tmp_dir / "input.p7m"
                p7m_path.write_bytes(data)

                extracted_path = tmp_dir / "payload.bin"
                ok, details = _extract_with_openssl_smime(p7m_path, extracted_path)
                if not ok:
                    ok, details = _extract_with_openssl_cms(p7m_path, extracted_path)
                if ok and extracted_path.exists() and extracted_path.stat().st_size > 0:
                    payload_bytes = extracted_path.read_bytes()
                    embedded_payload = True
                    signature_verified = True
                elif original_detached_bytes is not None:
                    original_path = tmp_dir / "original.bin"
                    original_path.write_bytes(original_detached_bytes)
                    detached_path = tmp_dir / "detached.bin"
                    ok, details = _verify_detached_with_openssl_smime(p7m_path, original_path, detached_path)
                    if not ok:
                        ok, details = _verify_detached_with_openssl_cms(p7m_path, original_path, detached_path)
                    if ok:
                        payload_bytes = original_detached_bytes
                        detached_signature = True
                        signature_verified = True
        except Exception as exc:
            details = str(exc)

    if payload_bytes is None:
        embedded = extract_signed_payload(data)
        if embedded:
            payload_bytes = embedded
            embedded_payload = True
            details = details or "Payload embedded estratto via parser ASN.1."
        elif original_detached_bytes is not None:
            payload_bytes = original_detached_bytes
            detached_signature = True
            details = details or "Firma detached rilevata con documento originale associato."

    if payload_bytes is None:
        message = (
            "Documento firmato digitalmente rilevato. Il contenuto non e' stato estratto automaticamente. "
            "Se la firma e' detached, serve il documento originale associato."
        )
        return SignedDocumentPayload(
            status=replace(
                base_status,
                detached_signature=bool(original_detached_bytes),
                message=message,
                technical_details=details or None,
            ),
            payload_bytes=None,
        )

    payload_source_name = original_detached_name or source_name
    payload_mime = payload_mime_from_bytes(payload_bytes, payload_source_name)
    payload_ext = payload_extension_from_mime(payload_mime, payload_source_name)
    payload_name = payload_name_from_source(payload_source_name if detached_signature else source_name, payload_ext)

    if detached_signature:
        message = "Firma detached rilevata. Documento originale associato disponibile per lettura."
    else:
        message = "Documento firmato digitalmente rilevato. Contenuto estratto correttamente."

    return SignedDocumentPayload(
        status=replace(
            base_status,
            extraction_ok=True,
            embedded_payload=embedded_payload,
            detached_signature=detached_signature,
            signature_verified=signature_verified,
            payload_available=True,
            payload_name=payload_name,
            payload_extension=payload_ext,
            payload_mime=payload_mime,
            payload_size=len(payload_bytes),
            message=message,
            technical_details=details or None,
        ),
        payload_bytes=payload_bytes,
    )


def verify_and_extract_p7m(
    p7m_path: str | Path,
    extracted_dir: str | Path,
    *,
    original_detached_path: str | Path | None = None,
) -> SignedDocumentStatus:
    source = Path(p7m_path)
    original_path = Path(original_detached_path) if original_detached_path else None
    payload = inspect_signed_document_bytes(
        source_name=source.name,
        source_path=str(source),
        data=source.read_bytes(),
        original_detached_bytes=original_path.read_bytes() if original_path and original_path.exists() else None,
        original_detached_name=original_path.name if original_path and original_path.exists() else None,
    )
    if not payload.status.payload_available or not payload.payload_bytes:
        return payload.status

    target_dir = Path(extracted_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / str(payload.status.payload_name or payload_name_from_source(source.name))
    tmp_path = target_dir / f".tmp-{target_path.name}"
    tmp_path.write_bytes(payload.payload_bytes)
    shutil.move(str(tmp_path), str(target_path))
    return replace(
        payload.status,
        payload_path=str(target_path),
        payload_size=target_path.stat().st_size,
    )


__all__ = [
    "SignedDocumentPayload",
    "SignedDocumentStatus",
    "extract_signed_payload",
    "inner_signed_name",
    "inner_signed_path",
    "inspect_signed_document_bytes",
    "is_p7m_filename",
    "payload_extension_from_mime",
    "payload_mime_from_bytes",
    "payload_name_from_source",
    "verify_and_extract_p7m",
]
