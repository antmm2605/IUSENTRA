"""Integration helpers for domain workflows that must emit forensic audit."""

from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

from .exceptions import AuditValidationError

try:
    from flask import current_app, g, has_app_context, has_request_context
except Exception:  # pragma: no cover
    current_app = None  # type: ignore[assignment]
    g = None  # type: ignore[assignment]

    def has_app_context() -> bool:
        return False

    def has_request_context() -> bool:
        return False

from .schemas import ActorContext, AuditFileRef, AuditKind, SourceContext
from .service import AuditService


def _cfg_bool(name: str, default: bool = False) -> bool:
    import os

    value = None
    if has_app_context() and current_app is not None:
        value = current_app.config.get(name)
    if value is None:
        value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _audit_runtime_enabled() -> bool:
    import os

    env = ""
    if has_app_context() and current_app is not None:
        env = str(current_app.config.get("AUDIT_ENV") or "")
    env = env or os.getenv("AUDIT_ENV", "development")
    return _cfg_bool("AUDIT_ENABLED", default=env.lower() == "production")


def _tenant_id(explicit: str = "") -> str:
    if explicit:
        return explicit
    if has_request_context() and g is not None:
        tenant = getattr(g, "tenant", None)
        if getattr(g, "tenant_context_missing", False):
            raise AuditValidationError("Contesto studio mancante per audit probatorio.")
        value = getattr(tenant, "id", "") or getattr(tenant, "slug", "") or getattr(g, "tenant_context_slug", "")
        if str(value or "").strip():
            return str(value).strip()
    raise AuditValidationError("Contesto studio mancante per audit probatorio.")


def _actor() -> ActorContext:
    if has_request_context() and g is not None:
        user = g.get("utente_corrente")
        if user is not None:
            return ActorContext(
                actor_id=str(getattr(user, "id", "") or getattr(user, "username", "") or ""),
                actor_type="user",
                display_name=str(getattr(user, "nome_completo", "") or getattr(user, "username", "") or ""),
            )
    return ActorContext(actor_id="system", actor_type="system")


def _service() -> AuditService:
    if has_app_context() and current_app is not None:
        cached = current_app.extensions.get("legal_audit_service")
        if isinstance(cached, AuditService):
            return cached
        service = AuditService.from_config(current_app.config)
        current_app.extensions["legal_audit_service"] = service
        return service
    return AuditService.from_config()


def _emit(
    *,
    kind: AuditKind,
    tenant_id: str,
    fascicolo_id: str,
    payload: dict[str, Any],
    files: list[AuditFileRef],
    module: str,
    idempotency_key: str,
) -> Any | None:
    if not _audit_runtime_enabled():
        return None
    return _service().emit_event(
        kind=kind,
        tenant_id=_tenant_id(tenant_id),
        fascicolo_id=fascicolo_id,
        actor=_actor(),
        payload=payload,
        files=files,
        source=SourceContext(
            service="iusentra",
            module=module,
            request_id=str(uuid.uuid4()),
            idempotency_key=idempotency_key,
        ),
        idempotency_key=idempotency_key,
    )


def emit_act_generated(
    *,
    fascicolo_id: str,
    atto_type: str,
    template_id: str,
    template_version: str,
    editor_version: str,
    output_format: str,
    file_path: str | Path,
    storage_ref: str,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    key = idempotency_key or f"ACT_GENERATED:{fascicolo_id}:{template_id}:{Path(file_path).name}"
    return _emit(
        kind=AuditKind.ACT_GENERATED,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={
            "atto_type": atto_type,
            "template_id": template_id,
            "template_version": template_version,
            "editor_version": editor_version,
            "output_format": output_format,
            "fascicolo_id": fascicolo_id,
        },
        files=[
            AuditFileRef(
                label=Path(file_path).name,
                storage_ref=storage_ref,
                path=file_path,
                mime="application/pdf" if str(file_path).lower().endswith(".pdf") else "",
            )
        ],
        module="atti",
        idempotency_key=key,
    )


def emit_pec_sent(
    *,
    fascicolo_id: str,
    message_id: str,
    sender_ref: str,
    recipients_hashes: list[str],
    subject_hash: str,
    provider: str,
    sent_at: str,
    eml_path: str | Path,
    storage_ref: str,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    return _emit(
        kind=AuditKind.PEC_SENT,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={
            "message_id": message_id,
            "sender_ref": sender_ref,
            "recipients_hashes": recipients_hashes,
            "subject_hash": subject_hash,
            "provider": provider,
            "sent_at": sent_at,
        },
        files=[AuditFileRef(label=Path(eml_path).name, storage_ref=storage_ref, path=eml_path, mime="message/rfc822")],
        module="pec",
        idempotency_key=idempotency_key or f"PEC_SENT:{fascicolo_id}:{message_id}",
    )


def emit_pec_receipt_acquired(
    *,
    fascicolo_id: str,
    receipt_type: str,
    provider_receipt_id: str,
    message_id: str,
    receipt_path: str | Path,
    storage_ref: str,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    return _emit(
        kind=AuditKind.PEC_RECEIPT_ACQUIRED,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={
            "receipt_type": receipt_type,
            "provider_receipt_id": provider_receipt_id,
            "message_id": message_id,
        },
        files=[AuditFileRef(label=Path(receipt_path).name, storage_ref=storage_ref, path=receipt_path)],
        module="pec.receipts",
        idempotency_key=idempotency_key or f"PEC_RECEIPT:{fascicolo_id}:{provider_receipt_id}",
    )


def emit_deposit_attempt(
    *,
    fascicolo_id: str,
    busta_path: str | Path,
    dati_atto_path: str | Path,
    storage_ref_prefix: str,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    return _emit(
        kind=AuditKind.DEPOSIT_ATTEMPT,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={"fascicolo_id": fascicolo_id},
        files=[
            AuditFileRef(label=Path(busta_path).name, storage_ref=f"{storage_ref_prefix}/busta.p7m", path=busta_path, mime="application/pkcs7-mime"),
            AuditFileRef(label=Path(dati_atto_path).name, storage_ref=f"{storage_ref_prefix}/DatiAtto.xml", path=dati_atto_path, mime="application/xml"),
        ],
        module="depositi",
        idempotency_key=idempotency_key or f"DEPOSIT_ATTEMPT:{fascicolo_id}:{Path(busta_path).name}",
    )


def emit_deposit_outcome(
    *,
    fascicolo_id: str,
    accepted: bool,
    portal: str,
    office: str,
    response_hash: str,
    registry: str = "",
    response_code: str = "",
    error_code: str = "",
    error_message_hash: str = "",
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    kind = AuditKind.DEPOSIT_ACCEPTED if accepted else AuditKind.DEPOSIT_FAILED
    payload = {
        "portal": portal,
        "office": office,
        "response_hash": response_hash,
    }
    if accepted:
        payload.update({"registry": registry, "response_code": response_code})
    else:
        payload.update({"error_code": error_code, "error_message_hash": error_message_hash})
    return _emit(
        kind=kind,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload=payload,
        files=[],
        module="depositi.esiti",
        idempotency_key=idempotency_key or f"{kind.value}:{fascicolo_id}:{response_hash}",
    )


def emit_incident(
    *,
    fascicolo_id: str,
    incident_id: str,
    related_event_id: str,
    reason_hash: str,
    updated: bool = False,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    kind = AuditKind.INCIDENT_UPDATED if updated else AuditKind.INCIDENT_OPENED
    return _emit(
        kind=kind,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={"incident_id": incident_id, "related_event_id": related_event_id, "reason_hash": reason_hash},
        files=[],
        module="incident",
        idempotency_key=idempotency_key or f"{kind.value}:{fascicolo_id}:{incident_id}:{related_event_id}",
    )


def emit_client_signature_acquired(
    *,
    fascicolo_id: str,
    signature_id: str,
    conferimento_id: str,
    original_sha256: str,
    signed_sha256: str,
    evidence_sha256: str,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    """Firma elettronica semplice acquisita dal Portale Cliente (evidence hash).

    Nel WORM finiscono solo gli hash: mai il tratto firma, l'IP o il token.
    """

    if not str(fascicolo_id or "").strip():
        return None
    return _emit(
        kind=AuditKind.CLIENT_SIGNATURE_ACQUIRED,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={
            "signature_id": signature_id,
            "conferimento_id": conferimento_id,
            "original_sha256": original_sha256,
            "signed_sha256": signed_sha256,
            "evidence_sha256": evidence_sha256,
        },
        files=[],
        module="client_portal.firma",
        idempotency_key=idempotency_key or f"CLIENT_SIGNATURE_ACQUIRED:{fascicolo_id}:{signature_id}",
    )


def emit_receipt_issued(
    *,
    fascicolo_id: str,
    receipt_id: str,
    invoice_id: str,
    issued_at: str,
    amount_hash: str,
    receipt_sha256: str,
    size_bytes: int,
    storage_ref: str,
    tenant_id: str = "",
    idempotency_key: str = "",
) -> Any | None:
    if not str(fascicolo_id or "").strip():
        return None
    return _emit(
        kind=AuditKind.RECEIPT_ISSUED,
        tenant_id=tenant_id,
        fascicolo_id=fascicolo_id,
        payload={
            "receipt_id": receipt_id,
            "invoice_id": invoice_id,
            "issued_at": issued_at,
            "amount_hash": amount_hash,
        },
        files=[
            AuditFileRef(
                label="ricevuta-cliente.pdf",
                storage_ref=storage_ref,
                sha256=receipt_sha256,
                size_bytes=size_bytes,
                mime="application/pdf",
            )
        ],
        module="fatturazione.ricevute",
        idempotency_key=idempotency_key or f"RECEIPT_ISSUED:{fascicolo_id}:{receipt_id}",
    )
