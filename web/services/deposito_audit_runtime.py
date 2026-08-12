"""Collegamento del pacchetto deposito al registro audit probatorio."""

from __future__ import annotations

from typing import Any

from flask import current_app

from audit.hashing import sha256_bytes
from audit.integrations import emit_deposit_attempt


def registra_audit_pacchetto_deposito(
    *,
    fascicolo_id: str,
    busta: Any,
    attachment_path: str,
    id_deposito: str,
    operation: str,
    message_id: str = "",
) -> dict[str, Any]:
    atto_msg_path = str(getattr(busta, "_last_atto_msg_path", "") or "").strip()
    if not attachment_path or not atto_msg_path:
        raise ValueError("Pacchetto deposito incompleto: Atto.enc o Atto.msg non disponibile per l'audit.")
    message_id_hash = sha256_bytes(message_id.encode("utf-8")) if message_id else ""
    try:
        result = emit_deposit_attempt(
            fascicolo_id=fascicolo_id,
            busta_path=attachment_path,
            atto_msg_path=atto_msg_path,
            storage_ref_prefix=f"depositi://fascicoli/{fascicolo_id}/{id_deposito}",
            operation=operation,
            deposit_id=id_deposito,
            message_id_hash=message_id_hash,
        )
    except Exception as exc:
        current_app.logger.exception(
            "Evento audit deposito non registrato fascicolo=%s deposito=%s operazione=%s: %s",
            fascicolo_id,
            id_deposito,
            operation,
            exc,
        )
        return {
            "audit_recorded": False,
            "avviso_audit": "Il pacchetto è stato preparato, ma il registro audit probatorio non ha acquisito l'evento.",
        }
    if result is None:
        return {"audit_recorded": False}
    return {
        "audit_recorded": True,
        "audit_event_id": str(getattr(result, "event_id", "") or ""),
        "audit_event_hash": str(getattr(result, "event_hash", "") or ""),
    }
