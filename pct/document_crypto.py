"""Cifratura condivisa dei documenti conservati a riposo."""

from __future__ import annotations

import hashlib
import os


ENC_MAGIC = b"PCTENC\x01"


def doc_key() -> bytes | None:
    """Restituisce la chiave AES-256 derivata dalla configurazione del tenant."""
    raw = os.getenv("PCT_DOC_KEY", "")
    if not raw:
        return None
    return hashlib.sha256(raw.encode()).digest()


def encrypt_doc(data: bytes) -> bytes:
    """Cifra i byte con AES-256-GCM; senza chiave mantiene il payload invariato."""
    key = doc_key()
    if not key:
        return data
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, data, None)
    return ENC_MAGIC + nonce + ciphertext


def decrypt_doc(data: bytes) -> bytes:
    """Decifra un documento IUSENTRA; i payload non cifrati restano invariati."""
    if not data.startswith(ENC_MAGIC):
        return data
    key = doc_key()
    if not key:
        raise ValueError("Documento cifrato ma PCT_DOC_KEY non configurata nel server.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    payload = data[len(ENC_MAGIC) :]
    if len(payload) < 13:
        raise ValueError("Documento cifrato non valido.")
    nonce, ciphertext = payload[:12], payload[12:]
    return AESGCM(key).decrypt(nonce, ciphertext, None)
