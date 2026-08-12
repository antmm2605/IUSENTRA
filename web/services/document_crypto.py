"""Compatibilita web per la cifratura condivisa dei documenti PCT."""

from pct.document_crypto import ENC_MAGIC, decrypt_doc, doc_key, encrypt_doc

_ENC_MAGIC = ENC_MAGIC

__all__ = ["ENC_MAGIC", "_ENC_MAGIC", "decrypt_doc", "doc_key", "encrypt_doc"]
