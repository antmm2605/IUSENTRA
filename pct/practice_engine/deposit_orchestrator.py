"""Preparazione e invio deposito con fail-closed in assenza di adapter reali."""

from __future__ import annotations

from typing import Any

from .deposit_readiness import run_predeposit_check
from .messages import NO_REAL_TRANSPORT
from .models import DepositStatus
from .repository import PracticeEngineRepository


def prepare_deposit(
    repository: PracticeEngineRepository,
    *,
    fascicolo: Any,
    profile: Any,
    cliente: Any | None = None,
    preventivo: Any | None = None,
    conferimento: Any | None = None,
    parcelle: list[Any] | None = None,
    fascicoli_manager: Any | None = None,
) -> dict[str, Any]:
    readiness = run_predeposit_check(
        repository,
        fascicolo=fascicolo,
        profile=profile,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        parcelle=parcelle or [],
        fascicoli_manager=fascicoli_manager,
    )
    status = DepositStatus.PRONTO.value if readiness["ready"] else DepositStatus.IN_PREPARAZIONE.value
    messages = [item.message for item in readiness["blockers"][:3]] or ["Predeposito completato: sessione pronta alla verifica finale."]
    session = repository.create_deposit_session(
        str(getattr(fascicolo, "id", "")),
        profile.code,
        profile.channel,
        status=status,
        transport_mode="predeposito",
        messages=messages,
    )
    repository.audit(str(getattr(fascicolo, "id", "")), "DEPOSIT_PREPARED", message="Sessione di predeposito preparata.", payload={"deposito_id": session.id, "ready": readiness["ready"]})
    return {"session": session, "readiness": readiness}


def send_deposit(
    repository: PracticeEngineRepository,
    *,
    session_id: str,
    fascicolo: Any,
    profile: Any,
    cliente: Any | None = None,
    preventivo: Any | None = None,
    conferimento: Any | None = None,
    parcelle: list[Any] | None = None,
    fascicoli_manager: Any | None = None,
    adapter: Any | None = None,
    accept_warnings: bool = False,
) -> dict[str, Any]:
    session = repository.get_deposit_session(session_id)
    if not session:
        raise KeyError(f"Sessione deposito '{session_id}' non trovata.")
    readiness = run_predeposit_check(
        repository,
        fascicolo=fascicolo,
        profile=profile,
        cliente=cliente,
        preventivo=preventivo,
        conferimento=conferimento,
        parcelle=parcelle or [],
        fascicoli_manager=fascicoli_manager,
        deposito_session=session,
    )
    if readiness["blockers"] or (readiness["warnings"] and not accept_warnings):
        session.status = DepositStatus.IN_PREPARAZIONE.value
        session.messages = [item.message for item in (readiness["blockers"] or readiness["warnings"])[:5]]
        repository.update_deposit_session(session)
        repository.add_timeline_event(session.id, session.fascicolo_id, "DEPOSIT_BLOCKED", session.status, session.messages[0])
        return {"sent": False, "session": session, "readiness": readiness, "message": session.messages[0]}
    if adapter is None or getattr(adapter, "simulated", True):
        session.status = DepositStatus.ERRORE.value
        session.transport_mode = "non_configurato"
        session.simulated = False
        session.real_transport = False
        session.messages = [NO_REAL_TRANSPORT]
        repository.update_deposit_session(session)
        repository.add_timeline_event(session.id, session.fascicolo_id, "REAL_TRANSPORT_MISSING", session.status, NO_REAL_TRANSPORT)
        return {"sent": False, "session": session, "readiness": readiness, "message": NO_REAL_TRANSPORT}
    result = adapter.send(fascicolo=fascicolo, profile=profile, session=session)
    session.status = DepositStatus.INVIATO.value
    session.transport_mode = str(getattr(adapter, "transport_mode", "reale"))
    session.real_transport = True
    session.simulated = False
    session.sent_at = str(result.get("sent_at") or "")
    session.messages = [str(result.get("message") or "Deposito inviato: in attesa delle ricevute ufficiali.")]
    repository.update_deposit_session(session)
    repository.add_timeline_event(session.id, session.fascicolo_id, "DEPOSIT_SENT", session.status, session.messages[0])
    return {"sent": True, "session": session, "readiness": readiness, "message": session.messages[0]}
