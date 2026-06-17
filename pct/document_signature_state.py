"""Regole comuni per riconoscere firme digitali realmente provate."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


SIGNED_CONTAINER_SUFFIXES = (".p7m", ".sig", ".pkcs7")


def _text(value: Any) -> str:
    return str(value or "").strip()


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
    return bool(
        payload.get("is_signed_container")
        or payload.get("signature_verified")
        or payload.get("verified")
        or payload.get("detached_signature")
        or payload.get("signed")
        or payload.get("firma_verificata")
        or payload.get("esito_firma_digitale")
        or payload.get("firmato_digitalmente_reale")
    )


def _mapping_signed_container(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    return bool(
        payload.get("is_signed_container")
        or payload.get("signed_container")
        or payload.get("container_signed")
        or payload.get("detached_signature")
        or str(payload.get("signature_type") or "").strip().lower() in {"cades", "cades_bes", "p7m", "pkcs7"}
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
        "signature_status",
        "signature_metadata",
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
        "signature_status",
        "signature_metadata",
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
