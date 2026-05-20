"""Workflow firma digitale: richiesta, registrazione esito e verifica strutturale."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


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
        return {"status": "NOT_REQUIRED", "errors": [], "warnings": []}
    errors: list[str] = []
    warnings: list[str] = []
    if not detected:
        errors.append("Firmatario rilevato mancante.")
    if expected and detected and expected != detected:
        errors.append("Firmatario rilevato non coerente con quello atteso.")
        return {"status": "MISMATCH_SIGNER", "errors": errors, "warnings": warnings}
    if not event.get("hash_after"):
        warnings.append("Hash del documento firmato non registrato.")
    if errors:
        return {"status": "ERROR", "errors": errors, "warnings": warnings}
    return {"status": "VERIFIED", "errors": [], "warnings": warnings}


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
            "signed_at": datetime.utcnow().isoformat(timespec="seconds"),
            "verified_at": datetime.utcnow().isoformat(timespec="seconds") if validation["status"] == "VERIFIED" else None,
            "evidence_document_id": evidence_document_id or None,
        },
    )
    return validation
