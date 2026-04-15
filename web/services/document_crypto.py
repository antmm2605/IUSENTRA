"""Utility di cifratura documenti per il runtime web."""

from __future__ import annotations

import os


_ENC_MAGIC = b"PCTENC\x01"


def doc_key() -> bytes | None:
    """Restituisce la chiave AES-256 da env var PCT_DOC_KEY, o None se non configurata."""
    raw = os.getenv("PCT_DOC_KEY", "")
    if not raw:
        return None
    import hashlib as _hl

    return _hl.sha256(raw.encode()).digest()


def encrypt_doc(data: bytes) -> bytes:
    """Cifra i byte del documento con AES-256-GCM. No-op se PCT_DOC_KEY non impostata."""
    key = doc_key()
    if not key:
        return data
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, data, None)
    return _ENC_MAGIC + nonce + ct


def decrypt_doc(data: bytes) -> bytes:
    """Decifra i byte del documento. No-op se il file non e' cifrato."""
    if not data.startswith(_ENC_MAGIC):
        return data
    key = doc_key()
    if not key:
        raise ValueError("Documento cifrato ma PCT_DOC_KEY non configurata nel server.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    payload = data[len(_ENC_MAGIC) :]
    nonce, ct = payload[:12], payload[12:]
    return AESGCM(key).decrypt(nonce, ct, None)
