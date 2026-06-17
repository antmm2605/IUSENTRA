"""Regole comuni per riconoscere firme digitali realmente provate."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


SIGNED_CONTAINER_SUFFIXES = (".p7m", ".sig", ".pkcs7")
_CADES_FORMATS = {"cades", "cades_bes", "p7m", "pkcs7", "cms", "signed_data"}
_PADES_FORMATS = {"pades", "pades_bes", "pdf", "pdf_signature"}
_FALSE_TEXT = {"", "0", "false", "no", "non_valida", "not_verified", "invalid", "errore", "error"}
_TRUE_TEXT = {"1", "true", "yes", "si", "sì", "ok", "valid", "valida", "verified", "verificata", "positivo"}
_SIGNATURE_FORMAT_KEYS = ("signature_format", "signature_type", "formato", "format", "tipo_firma")
_VERIFIED_KEYS = (
    "signature_verified",
    "verified",
    "firma_verificata",
    "pades_verified",
    "pdf_signature_verified",
    "firmato_digitalmente_reale",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        text = value.strip().lower()
        if text in _FALSE_TEXT:
            return False
        if text in _TRUE_TEXT:
            return True
    return bool(value)


def _signature_format(payload: Mapping[str, Any]) -> str:
    for key in _SIGNATURE_FORMAT_KEYS:
        value = _text(payload.get(key)).lower().replace("-", "_")
        if value:
            return value
    return ""


def _has_verified_signature_evidence(payload: Mapping[str, Any]) -> bool:
    if any(_truthy(payload.get(key)) for key in _VERIFIED_KEYS):
        return True
    esito = _text(payload.get("esito_firma_digitale") or payload.get("signature_status")).lower()
    return bool(esito and esito not in _FALSE_TEXT and esito in _TRUE_TEXT)


def is_signed_container_name(*names: Any) -> bool:
    """True solo se il nome indica un contenitore firmato reale."""
    for name in names:
        text = _text(name).lower()
        if text and text.endswith(SIGNED_CONTAINER_SUFFIXES):
            return True
        path_name = Path(text).name if text else ""
        if path_name and path_name.endswith(SIGNED_CONTAINER_SUFFIXES):
            return True
    return False


def _mapping_truthy_signature(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    signature_format = _signature_format(payload)
    if _mapping_signed_container(payload):
        return True
    if signature_format in _PADES_FORMATS:
        return _has_verified_signature_evidence(payload)
    if signature_format in _CADES_FORMATS:
        return _has_verified_signature_evidence(payload) or _truthy(payload.get("is_signed_container"))
    if _truthy(payload.get("pades_verified")) or _truthy(payload.get("pdf_signature_verified")):
        return True
    return False


def _mapping_signed_container(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    signature_format = _signature_format(payload)
    return bool(
        _truthy(payload.get("is_signed_container"))
        or _truthy(payload.get("signed_container"))
        or _truthy(payload.get("container_signed"))
        or _truthy(payload.get("detached_signature"))
        or signature_format in _CADES_FORMATS
    )


def document_has_signed_container(document: Any, *display_names: Any) -> bool:
    """True se la firma rilevata e' un contenitore CAdES/PKCS#7."""
    candidate_names = [
        *display_names,
        getattr(document, "nome", ""),
        getattr(document, "nome_originale", ""),
        getattr(document, "nome_portale", ""),
        getattr(document, "percorso", ""),
    ]
    if is_signed_container_name(*candidate_names):
        return True

    for attr in (
        "signed_status",
        "signed_ui",
        "firma_status",
        "firma_esito",
        "metadati_firma",
        "signature_metadata",
        "signature_status",
    ):
        if _mapping_signed_container(getattr(document, attr, None)):
            return True

    return False


def document_has_real_digital_signature(document: Any, *display_names: Any) -> bool:
    """True solo davanti a contenitore firmato o metadato/esito tecnico reale."""
    candidate_names = [
        *display_names,
        getattr(document, "nome", ""),
        getattr(document, "nome_originale", ""),
        getattr(document, "nome_portale", ""),
        getattr(document, "percorso", ""),
    ]
    if is_signed_container_name(*candidate_names):
        return True

    for attr in (
        "signed_status",
        "signed_ui",
        "firma_status",
        "firma_esito",
        "metadati_firma",
        "signature_metadata",
        "signature_status",
    ):
        if _mapping_truthy_signature(getattr(document, attr, None)):
            return True

    return False


__all__ = [
    "SIGNED_CONTAINER_SUFFIXES",
    "document_has_signed_container",
    "document_has_real_digital_signature",
    "is_signed_container_name",
]
