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


def document_bytes_have_real_digital_signature(data: bytes, *display_names: Any) -> bool:
    """Verifica CAdES/PAdES sui byte reali; il nome file da solo non basta."""
    if not data:
        return False
    try:
        from pct.firma import busta_cades_valida

        if busta_cades_valida(data):
            return True
    except Exception:
        pass
    if is_signed_container_name(*display_names):
        return False
    if data[:8].startswith(b"%PDF-"):
        try:
            from pct.firma import analizza_firma_documento

            filename = next((_text(name) for name in display_names if _text(name)), "")
            return any(
                item.get("content_digest_verified") is True
                and item.get("cryptographic_signature_verified") is True
                for item in analizza_firma_documento(data, filename)
            )
        except Exception:
            return False
    return False


def cades_crittograficamente_valida(data: bytes) -> bool:
    """Verifica crittografica di una busta CAdES con il documento incorporato."""
    try:
        from asn1crypto import cms

        info = cms.ContentInfo.load(data)
        if info["content_type"].native != "signed_data":
            return False
        signed_data = info["content"]
        return _cades_signatures_are_cryptographically_valid(signed_data, _cades_embedded_content(signed_data))
    except Exception:
        return False


__all__ = [
    "cades_crittograficamente_valida",
    "SIGNED_CONTAINER_SUFFIXES",
    "document_bytes_have_real_digital_signature",
    "document_has_signed_container",
    "document_has_real_digital_signature",
    "is_signed_container_name",
]


def _cades_embedded_content(signed_data: Any) -> bytes:
    content = signed_data["encap_content_info"]["content"]
    if content.native is None:
        raise ValueError("La busta CAdES è detached e non contiene il documento.")
    embedded = content.native
    return embedded if isinstance(embedded, bytes) else bytes(content.contents)


def _cades_signer_certificate(signer_info: Any, certificates: Any) -> Any | None:
    sid = signer_info["sid"]
    for certificate_choice in certificates or []:
        if certificate_choice.name != "certificate":
            continue
        certificate = certificate_choice.chosen
        if sid.name == "issuer_and_serial_number":
            issuer_serial = sid.chosen
            if (
                certificate.serial_number == issuer_serial["serial_number"].native
                and certificate.issuer.dump() == issuer_serial["issuer"].dump()
            ):
                return certificate
        elif sid.name == "subject_key_identifier":
            key_identifier = getattr(certificate, "key_identifier", None)
            if key_identifier and key_identifier == sid.chosen.native:
                return certificate
    return None


def _cades_signatures_are_cryptographically_valid(signed_data: Any, content: bytes) -> bool:
    import hashlib

    try:
        from pyhanko.sign.validation.generic_cms import validate_sig_integrity
    except Exception:
        return False

    content_type = signed_data["encap_content_info"]["content_type"].native
    for signer_info in signed_data["signer_infos"]:
        certificate = _cades_signer_certificate(
            signer_info,
            signed_data["certificates"],
        )
        if certificate is None:
            return False
        digest_algorithm = str(
            signer_info["digest_algorithm"]["algorithm"].native or ""
        ).lower().replace("-", "")
        try:
            digest = hashlib.new(digest_algorithm, content).digest()
            intact, valid = validate_sig_integrity(
                signer_info,
                certificate,
                expected_content_type=content_type,
                actual_digest=digest,
            )
        except Exception:
            return False
        if not intact or not valid:
            return False
    return True


def _verify_parallel_cades_signature(original: bytes, signed: bytes) -> None:
    from collections import Counter

    from asn1crypto import cms

    try:
        original_info = cms.ContentInfo.load(original, strict=True)
        signed_info = cms.ContentInfo.load(signed, strict=True)
        if (
            original_info["content_type"].native != "signed_data"
            or signed_info["content_type"].native != "signed_data"
        ):
            raise ValueError
    except Exception as exc:
        raise ValueError("La firma aggiuntiva non è una busta CAdES valida.") from exc

    original_data = original_info["content"]
    signed_data = signed_info["content"]
    original_content = _cades_embedded_content(original_data)
    signed_content = _cades_embedded_content(signed_data)

    try:
        nested = cms.ContentInfo.load(signed_content, strict=True)
    except Exception:
        nested = None
    if nested is not None and nested["content_type"].native == "signed_data":
        raise ValueError("La cofirma CAdES annidata non è ammessa.")
    if signed_content != original_content or signed_content == original:
        raise ValueError(
            "La nuova firma CAdES non conserva lo stesso contenuto incapsulato."
        )

    original_signers = Counter(
        signer.dump() for signer in original_data["signer_infos"]
    )
    signed_signers = Counter(
        signer.dump() for signer in signed_data["signer_infos"]
    )
    if (
        sum(signed_signers.values()) <= sum(original_signers.values())
        or any(signed_signers[item] < count for item, count in original_signers.items())
    ):
        raise ValueError(
            "La nuova busta CAdES non conserva tutte le firme precedenti come firme parallele."
        )

    original_certificates = Counter(
        certificate.dump() for certificate in original_data["certificates"] or []
    )
    signed_certificates = Counter(
        certificate.dump() for certificate in signed_data["certificates"] or []
    )
    if any(
        signed_certificates[item] < count
        for item, count in original_certificates.items()
    ):
        raise ValueError(
            "La nuova busta CAdES non conserva i certificati delle firme precedenti."
        )
    if not _cades_signatures_are_cryptographically_valid(signed_data, signed_content):
        raise ValueError(
            "La nuova busta CAdES contiene una firma non verificabile sul documento."
        )

def verify_additional_signature(original: bytes, signed: bytes, filename: str) -> None:
    """Verifica che la firma aggiunta conservi documento e firme già presenti."""
    if not original or original == signed:
        raise ValueError("Il file non contiene una nuova firma.")
    if original.startswith(b"%PDF-") and signed.startswith(original):
        import io

        from pyhanko.pdf_utils.reader import PdfFileReader

        from pct.firma import analizza_firma_documento

        before = PdfFileReader(io.BytesIO(original)).embedded_signatures
        after = PdfFileReader(io.BytesIO(signed)).embedded_signatures
        preserved = {
            (item.field_name, bytes(item.sig_object["/Contents"])) for item in before
        }
        actual = {
            (item.field_name, bytes(item.sig_object["/Contents"])) for item in after
        }
        evidence = analizza_firma_documento(signed, filename)
        if (before and len(after) > len(before) and preserved.issubset(actual)
                and len(evidence) == len(after)
                and all(item.get("content_digest_verified") and item.get("cryptographic_signature_verified")
                        for item in evidence)):
            return
    else:
        from pct.firma import busta_cades_valida

        if busta_cades_valida(original) or is_signed_container_name(filename):
            _verify_parallel_cades_signature(original, signed)
            return
    raise ValueError("La nuova firma non conserva integralmente il documento e le firme precedenti.")
