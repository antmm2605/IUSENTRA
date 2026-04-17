"""Utilità di estrazione testo da documenti fascicolo per Lex.

Gestisce: PDF, PDF.p7m, DOCX, TXT.
Pipeline: leggi bytes → decifra (AES-256-GCM) → estrai payload p7m → OCR/testo.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from pathlib import Path
from typing import Any

_ENC_MAGIC = b"PCTENC\x01"
_MAX_TEXT_CHARS = 12_000   # limite caratteri per singolo documento
_MAX_PAGES = 15


def _doc_key() -> bytes | None:
    raw = str(os.getenv("PCT_DOC_KEY", "") or "").strip()
    if not raw:
        return None
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _decrypt(data: bytes) -> bytes:
    if not data.startswith(_ENC_MAGIC):
        return data
    key = _doc_key()
    if not key:
        return data  # documento cifrato ma chiave non configurata: restituiamo as-is
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        payload = data[len(_ENC_MAGIC):]
        nonce, ciphertext = payload[:12], payload[12:]
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception:
        return data


def _extract_p7m(data: bytes, filename: str) -> bytes:
    """Estrae il payload interno da un file .p7m (CAdES)."""
    try:
        from pct.firme_cades import inspect_signed_document_bytes
        result = inspect_signed_document_bytes(
            source_name=filename,
            source_path="",
            data=data,
        )
        if result.status.payload_available and result.payload_bytes:
            return result.payload_bytes
    except Exception:
        pass
    # Fallback: asn1crypto
    try:
        from pct.firme_cades import extract_signed_payload
        inner = extract_signed_payload(data)
        if inner:
            return inner
    except Exception:
        pass
    return data


def _pdf_to_text(data: bytes) -> str:
    lines: list[str] = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= _MAX_PAGES:
                    break
                text = (page.extract_text() or "").strip()
                if text:
                    lines.append(text)
                else:
                    # OCR fallback
                    try:
                        import pytesseract
                        img = page.to_image(resolution=150).original
                        ocr_text = pytesseract.image_to_string(img, lang="ita").strip()
                        if ocr_text:
                            lines.append(ocr_text)
                    except Exception:
                        pass
    except Exception:
        pass
    return "\n\n".join(lines)


def _docx_to_text(data: bytes) -> str:
    try:
        import mammoth
        result = mammoth.convert_to_markdown(io.BytesIO(data))
        return str(result.value or "").strip()
    except Exception:
        pass
    try:
        import zipfile
        from xml.etree import ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if "word/document.xml" in z.namelist():
                xml = z.read("word/document.xml")
                root = ET.fromstring(xml)
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                return " ".join(t.text or "" for t in root.findall(".//w:t", ns)).strip()
    except Exception:
        pass
    return ""


def _normalize(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", str(text or ""))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:_MAX_TEXT_CHARS]


def extract_text_from_bytes(data: bytes, filename: str) -> str:
    """Estrae testo da bytes di un documento (PDF, p7m, DOCX, TXT)."""
    data = _decrypt(data)
    name_lower = filename.lower()

    # p7m: estrai payload interno, poi ricaduta su PDF se il payload è PDF
    if name_lower.endswith(".p7m"):
        inner = _extract_p7m(data, filename)
        inner_name = filename[:-4] if filename.lower().endswith(".p7m") else filename
        return extract_text_from_bytes(inner, inner_name)

    if name_lower.endswith(".pdf"):
        return _normalize(_pdf_to_text(data))

    if name_lower.endswith((".docx", ".doc")):
        return _normalize(_docx_to_text(data))

    if name_lower.endswith(".txt") or name_lower.endswith(".xml"):
        return _normalize(data.decode("utf-8", errors="replace"))

    # Prova come testo
    try:
        decoded = data.decode("utf-8", errors="strict")
        if decoded.strip():
            return _normalize(decoded)
    except Exception:
        pass
    return ""


def read_document_file(file_path: Path) -> bytes:
    """Legge un file dal disco e decifra se necessario."""
    data = file_path.read_bytes()
    return _decrypt(data)


def extract_text_from_file(file_path: Path) -> str:
    """Legge e converte in testo un file dal disco (PDF, p7m, DOCX, TXT)."""
    try:
        data = file_path.read_bytes()
        return extract_text_from_bytes(data, file_path.name)
    except Exception as exc:
        return f"[Impossibile leggere il file: {exc}]"


def get_fascicoli_store():
    """Restituisce il GestioneFascicoli dal contesto Flask."""
    from web.helpers import get_fascicoli
    return get_fascicoli()
