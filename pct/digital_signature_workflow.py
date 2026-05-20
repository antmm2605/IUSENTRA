"""Workflow firma digitale: richiesta, registrazione esito e verifica strutturale."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


class SignatureStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED_PENDING = "REQUIRED_PENDING"
    SIGNED_UNVERIFIED = "SIGNED_UNVERIFIED"
    VERIFIED = "VERIFIED"
    INVALID = "INVALID"
    MISMATCH_SIGNER = "MISMATCH_SIGNER"
    EXPIRED_CERTIFICATE = "EXPIRED_CERTIFICATE"
    ERROR = "ERROR"


SIGNATURE_STATUSES: tuple[str, ...] = tuple(status.value for status in SignatureStatus)
SIGNATURE_REQUIRED_ROLES = {"atto_principale", "ricorso", "procura", "dati_atto", "deposit_package"}
TELEMATIC_CHANNEL_PREFIXES = {"010", "011", "012", "014", "015", "017", "019", "020", "030", "050", "051", "052", "053", "055", "059"}
FORBIDDEN_SECRET_KEYS = {"pin", "password", "token", "secret", "credential", "credentials", "otp"}


def _has_secret(payload: dict[str, Any]) -> bool:
    return any(str(key).lower() in FORBIDDEN_SECRET_KEYS for key in payload)


def is_signature_required(procedure_code: str, xsd_code: str | None, document_role: str) -> bool:
    role = str(document_role or "").strip().lower()
    if role in SIGNATURE_REQUIRED_ROLES:
        return True
    if str(xsd_code or "")[:3] in TELEMATIC_CHANNEL_PREFIXES and role not in {"nota_interna", "bozza"}:
        return True
    return "PCT" in str(procedure_code or "").upper() and role != "bozza"


def create_signature_requirement(
    repo: ProcedureLifecycleRepository,
    *,
    fascicolo_id: str,
    document_id: str,
    procedure_code: str,
    xsd_code: str | None,
    document_role: str,
    signer_expected: str = "",
    **payload: Any,
) -> int:
    if _has_secret(payload):
        raise ValueError("Credenziali, PIN, password o token non possono essere conservati nel workflow firma.")
    required = is_signature_required(procedure_code, xsd_code, document_role)
    return repo.add_signature_event(
        {
            "fascicolo_id": fascicolo_id,
            "document_id": document_id,
            "required": 1 if required else 0,
            "signer_expected": signer_expected or None,
            "verification_status": "REQUIRED_PENDING" if required else "NOT_REQUIRED",
            "notes": f"Ruolo documento: {document_role}",
        }
    )


def verify_signature_event_consistency(event: dict[str, Any]) -> dict[str, Any]:
    expected = str(event.get("signer_expected") or "").strip().lower()
    detected = str(event.get("signer_detected") or "").strip().lower()
    if int(event.get("required") or 0) == 0:
        return {"status": SignatureStatus.NOT_REQUIRED.value, "errors": [], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    if event.get("certificate_expired"):
        errors.append("Certificato scaduto.")
        return {"status": SignatureStatus.EXPIRED_CERTIFICATE.value, "errors": errors, "warnings": warnings}
    if event.get("signature_invalid"):
        errors.append("Firma non valida.")
        return {"status": SignatureStatus.INVALID.value, "errors": errors, "warnings": warnings}
    if not detected:
        errors.append("Firmatario rilevato mancante.")
    if expected and detected and expected != detected:
        errors.append("Firmatario rilevato non coerente con quello atteso.")
        return {"status": SignatureStatus.MISMATCH_SIGNER.value, "errors": errors, "warnings": warnings}
    if not event.get("hash_after"):
        warnings.append("Hash del documento firmato non registrato.")
    if errors:
        return {"status": SignatureStatus.ERROR.value, "errors": errors, "warnings": warnings}
    return {"status": SignatureStatus.VERIFIED.value, "errors": [], "warnings": warnings}


def record_signature_result(
    repo: ProcedureLifecycleRepository,
    event_id: int,
    *,
    signer_detected: str,
    hash_after: str,
    signature_format: str = "PAdES",
    certificate_serial: str = "",
    signer_tax_code: str = "",
    evidence_document_id: str = "",
    **payload: Any,
) -> dict[str, Any]:
    if _has_secret(payload):
        raise ValueError("Credenziali, PIN, password o token non possono essere conservati nel workflow firma.")
    with repo.connect() as conn:
        event = repo._fetch_one(conn, "SELECT * FROM digital_signature_events WHERE id = ?", (event_id,)) or {}
    candidate = {
        **event,
        "signer_detected": signer_detected,
        "hash_after": hash_after,
        "signature_format": signature_format,
        "certificate_serial": certificate_serial,
        "signer_tax_code": signer_tax_code,
        "evidence_document_id": evidence_document_id,
    }
    validation = verify_signature_event_consistency(candidate)
    repo.update_signature_event(
        event_id,
        {
            "signer_detected": signer_detected,
            "signer_tax_code": signer_tax_code or None,
            "signature_format": signature_format,
            "certificate_serial": certificate_serial or None,
            "hash_after": hash_after,
            "verification_status": validation["status"],
            "signed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "verified_at": datetime.now(UTC).isoformat(timespec="seconds") if validation["status"] == "VERIFIED" else None,
            "evidence_document_id": evidence_document_id or None,
        },
    )
    return validation


def assert_required_signatures_verified(
    repo: ProcedureLifecycleRepository,
    fascicolo_id: str,
    *,
    document_ids: tuple[str, ...] | list[str] | None = None,
) -> None:
    expected = set(document_ids or [])
    events = repo.list_signature_events(fascicolo_id)
    required_events = [
        event
        for event in events
        if int(event.get("required") or 0) == 1 and (not expected or str(event.get("document_id") or "") in expected)
    ]
    if expected:
        seen = {str(event.get("document_id") or "") for event in required_events}
        missing = sorted(expected - seen)
        if missing:
            raise ValueError(f"Firma digitale richiesta ma non censita per documenti: {', '.join(missing)}")
    not_verified = [
        str(event.get("document_id") or event.get("id") or "")
        for event in required_events
        if event.get("verification_status") != SignatureStatus.VERIFIED.value
    ]
    if not_verified:
        raise ValueError(f"Firma digitale richiesta ma non VERIFIED per documenti: {', '.join(not_verified)}")
