"""Validazione minima del contenitore ministeriale Atto.enc."""

from __future__ import annotations

from typing import Any


CMS_ENVELOPED_DATA_OID = b"\x06\x09*\x86H\x86\xf7\r\x01\x07\x03"


def _asn1crypto_cms_info(payload: bytes) -> dict[str, Any] | None:
    try:
        from asn1crypto import cms
    except Exception:
        return None
    try:
        content_info = cms.ContentInfo.load(payload)
        if content_info["content_type"].native != "enveloped_data":
            return {"valid": False, "reason": "content_type_non_enveloped_data"}
        enveloped_data = content_info["content"]
        encrypted_info = enveloped_data["encrypted_content_info"]
        algorithm = encrypted_info["content_encryption_algorithm"]["algorithm"]
        return {
            "valid": encrypted_info["content_type"].native == "data",
            "content_type": encrypted_info["content_type"].native,
            "encryption_algorithm": algorithm.native,
            "encryption_algorithm_oid": algorithm.dotted,
            "recipients": len(enveloped_data["recipient_infos"]),
        }
    except Exception as exc:
        return {"valid": False, "reason": f"cms_parse_error:{exc.__class__.__name__}"}


def inspect_atto_enc_payload(payload: bytes) -> dict[str, Any]:
    """Restituisce un audit leggero del CMS Atto.enc senza decifrare la busta."""

    data = bytes(payload or b"")
    info = _asn1crypto_cms_info(data)
    if info is not None:
        info["size_bytes"] = len(data)
        return info
    heuristic_ok = len(data) > 128 and data[:1] == b"\x30" and CMS_ENVELOPED_DATA_OID in data[:512]
    return {
        "valid": heuristic_ok,
        "size_bytes": len(data),
        "content_type": "enveloped_data" if heuristic_ok else "",
        "encryption_algorithm": "",
        "encryption_algorithm_oid": "",
        "recipients": None,
        "reason": "" if heuristic_ok else "cms_enveloped_data_non_riconoscibile",
    }


def is_atto_enc_cms_enveloped_data(payload: bytes) -> bool:
    """True solo se Atto.enc ha struttura CMS EnvelopedData riconoscibile."""

    return inspect_atto_enc_payload(payload).get("valid") is True
