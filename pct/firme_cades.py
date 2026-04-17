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


def _unwrap_octet_string(raw: bytes) -> bytes | None:
    """Rimuove un eventuale layer OctetString wrapper (double-wrap comune nei p7m italiani)."""
    if not raw or raw[0] != 0x04:
        return None
    try:
        # Calcola la lunghezza del tag+len header per trovare il payload puro
        idx = 1
        if raw[idx] & 0x80:
            n = raw[idx] & 0x7F
            idx += 1 + n
        else:
            idx += 1
        if idx < len(raw):
            return raw[idx:]
    except Exception:
        pass
    return None


def _extract_via_asn1crypto(data: bytes) -> bytes | None:
    """Estrazione payload via asn1crypto con gestione double-wrap."""
    try:
        from asn1crypto import cms  # type: ignore
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

        # Tentativo 1: .native standard
        native = getattr(content, "native", None)
        if isinstance(native, bytes) and native:
            # Controlla double-wrap (OctetString che wrappa un altro OctetString)
            if native[0] == 0x04:
                inner = _unwrap_octet_string(native)
                if inner and len(inner) > 4:
                    return inner
            return native

        # Tentativo 2: accesso diretto ai contenuti grezzi
        raw = getattr(content, "contents", None)
        if isinstance(raw, bytes) and raw:
            if raw[0] == 0x04:
                inner = _unwrap_octet_string(raw)
                if inner and len(inner) > 4:
                    return inner
            return raw

        if isinstance(content, bytes) and content:
            return content

    except Exception:
        pass
    return None


def _extract_via_magic_bytes(data: bytes) -> bytes | None:
    """Cerca magic bytes di formati noti nel blob CAdES (ultima risorsa)."""
    # PDF
    idx = data.find(b"%PDF")
    if idx >= 0:
        snippet = data[idx:]
        if len(snippet) > 64 and (b"%%EOF" in snippet or b"endobj" in snippet or b"stream" in snippet):
            return snippet
    # ZIP / DOCX
    idx = data.find(b"PK\x03\x04")
    if idx >= 0 and len(data) - idx > 512:
        return data[idx:]
    # XML (DatiAtto.xml e simili del PST)
    for marker in (b"<?xml", b"<DatiAtto", b"<Deposito", b"<atto", b"<Atto"):
        idx = data.find(marker)
        if idx >= 0 and len(data) - idx > 32:
            return data[idx:]
    return None


def extract_signed_payload(data: bytes) -> bytes | None:
    """Estrae il payload firmato da una busta CAdES (.p7m).

    Strategia multi-livello per la massima compatibilità con i p7m
    generati dai sistemi giudiziari italiani (PST, PDP, PAT):
    1. asn1crypto (con gestione double-wrap)
    2. ricerca diretta magic bytes nel blob ASN.1
    """
    result = _extract_via_asn1crypto(data)
    if result:
        return result
    return _extract_via_magic_bytes(data)


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


def _extract_with_openssl_cms_auto(p7m_path: Path, output_path: Path) -> tuple[bool, str]:
    """CMS senza -inform DER (auto-detect BER/DER/PEM)."""
    return _run_command(
        [
            "openssl", "cms", "-verify", "-binary",
            "-in", str(p7m_path), "-noverify",
            "-out", str(output_path),
        ]
    )


def _extract_with_openssl_smime_auto(p7m_path: Path, output_path: Path) -> tuple[bool, str]:
    """SMIME senza -inform DER (auto-detect)."""
    return _run_command(
        [
            "openssl", "smime", "-verify",
            "-in", str(p7m_path), "-noverify",
            "-out", str(output_path),
        ]
    )


def _extract_with_openssl_pkcs7(p7m_path: Path, output_path: Path) -> tuple[bool, str]:
    """Usa il subcomando pkcs7 per estrarre il contenuto embedded."""
    return _run_command(
        [
            "openssl", "pkcs7", "-inform", "DER",
            "-in", str(p7m_path), "-print",
            "-out", str(output_path),
        ]
    )
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
                # Strategia A: smime DER (standard PKCS7)
                ok, details = _extract_with_openssl_smime(p7m_path, extracted_path)
                # Strategia B: cms DER -binary (CAdES-BES binario)
                if not ok or not (extracted_path.exists() and extracted_path.stat().st_size > 0):
                    ok, details = _extract_with_openssl_cms(p7m_path, extracted_path)
                # Strategia C: cms senza -inform (auto BER/DER/PEM)
                if not ok or not (extracted_path.exists() and extracted_path.stat().st_size > 0):
                    ok, details = _extract_with_openssl_cms_auto(p7m_path, extracted_path)
                # Strategia D: smime senza -inform (auto-detect)
                if not ok or not (extracted_path.exists() and extracted_path.stat().st_size > 0):
                    ok, details = _extract_with_openssl_smime_auto(p7m_path, extracted_path)
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
