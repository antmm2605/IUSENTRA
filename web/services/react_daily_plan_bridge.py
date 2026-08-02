"""Bridge React per il piano del giorno (Lex Oggi).

Le letture servono SOLO lo snapshot materializzato dal repository Daily Plan
(mai collettori, OCR o LLM nel percorso GET). Le scritture applicative
diventano proposte nella coda approvazioni Workflow Agents: nessuna azione
legale parte in automatico.
"""

from __future__ import annotations

from typing import Any

from pct.daily_plan.models import ITEM_STATUS_TRANSITIONS
from pct.daily_plan.repository import InvalidStatusTransition, TenantMismatchError
from pct.daily_plan.serializers import (
    item_detail_payload,
    item_summary_payload,
    plan_missing_payload,
    plan_summary_payload,
)
from web.services.daily_plan_runtime import (
    current_tenant_label,
    repository_for_current_request,
    service_for_current_request,
)

# azione UI → nuovo stato dell'attività (transizioni dirette, senza scritture
# nei dati di dominio)
STATUS_ACTIONS = {
    "accept": "accepted",
    "start": "in_progress",
    "complete": "completed",
    "delegate": "delegated",
    "snooze": "snoozed",
    "reject": "rejected",
}

# azione UI → tool applicativo (sempre proposta approvabile, mai esecuzione
# diretta). Whitelist chiusa: invio PEC, firma, deposito, cancellazioni e
# fatture definitive NON sono raggiungibili da qui.
DOMAIN_ACTIONS = {
    "create_task": "create_task",
    "create_deadline": "create_deadline",
    "create_calendar_proposal": "create_task",
    "create_pec_draft": "create_pec_draft",
}


class DailyPlanNotFound(KeyError):
    pass


class DailyPlanRefreshJobNotFound(KeyError):
    pass


class DailyPlanForbidden(PermissionError):
    pass


def build_react_daily_plan_payload(*, target_date: str = "", user_id: str) -> dict[str, Any]:
    service = service_for_current_request()
    target = target_date or service.clock.today().isoformat()
    plan = service.read_plan(user_id=user_id, target_date=target)
    if plan is None:
        return plan_missing_payload(target, user_id)
    return plan_summary_payload(plan)


def daily_plan_coverage_payload(*, target_date: str = "") -> dict[str, Any]:
    repo = repository_for_current_request()
    watermarks = repo.get_watermarks()
    return {
        "ok": True,
        "tenant_pronto": True,
        "fonti": {
            source: {
                "watermark": str(row.get("watermark") or ""),
                "ultimo_successo": str(row.get("last_success_at") or ""),
                "stato": str(row.get("last_status") or "never"),
                "ultimo_errore": str(row.get("last_error") or ""),
            }
            for source, row in watermarks.items()
        },
        "elementi_in_attesa": repo.pending_dirty_count(),
    }


def daily_plan_item_detail_payload(item_id: str) -> dict[str, Any]:
    repo = repository_for_current_request()
    item = repo.get_item(item_id)
    if item is None:
        raise DailyPlanNotFound(item_id)
    return {"ok": True, "attivita": item_detail_payload(item)}


def daily_plan_backlog_payload(
    *, target_date: str = "", user_id: str, cursor: str = "", limit: int = 50
) -> dict[str, Any]:
    service = service_for_current_request()
    target = target_date or service.clock.today().isoformat()
    page = service.repository.list_backlog_page(
        target, assigned_user_id=user_id, cursor=cursor, limit=limit
    )
    return {
        "ok": True,
        "items": [item_summary_payload(i) for i in page["items"]],
        "next_cursor": page["next_cursor"],
        "total_matching": page["total_matching"],
        "truncated": page["truncated"],
    }


def enqueue_daily_plan_refresh(
    *, mode: str, actor: str, target_date: str = "", idempotency_key: str = ""
) -> dict[str, Any]:
    repo = repository_for_current_request()
    job_type = "full_rebuild" if mode == "full" else "incremental_refresh"
    outcome = repo.enqueue_job(
        job_type,
        requested_by=actor,
        idempotency_key=idempotency_key,
        payload={"target_date": target_date} if target_date else {},
        budget={"max_entities": 200, "max_seconds": 60},
    )
    return {
        "ok": True,
        "accettato": True,
        "job_id": outcome["job_id"],
        "stato": outcome["status"],
        "data": target_date,
        "gia_in_coda": bool(outcome.get("replayed")),
    }


def mark_daily_plan_refresh_scheduler_disabled(job_id: str) -> None:
    """Chiude subito una richiesta non eseguibile per scelta dello studio."""
    repo = repository_for_current_request()
    job = repo.get_job(job_id)
    if job is None or str(job.get("status") or "") not in {"queued", "running"}:
        return
    repo.finish_job(
        job_id,
        status="failed",
        report={"ok": False, "code": "scheduler_disabled"},
    )


def daily_plan_refresh_status_payload(job_id: str) -> dict[str, Any]:
    """Stato leggero e tenant-aware della richiesta di aggiornamento.

    Non espone errori tecnici, path o contenuti delle fonti: alla pagina serve
    solo un esito onesto dell'elaborazione automatica e un riepilogo numerico.
    """
    repo = repository_for_current_request()
    job = repo.get_job(job_id)
    if job is None:
        raise DailyPlanRefreshJobNotFound(job_id)

    status = str(job.get("status") or "queued").strip().lower()
    report = dict(job.get("report") or {})
    target_date = str((job.get("payload") or {}).get("target_date") or "")
    messages = {
        "queued": (
            "Aggiornamento in coda: il piano resta consultabile e l'elaborazione automatica prosegue senza bloccare la pagina."
        ),
        "running": "Aggiornamento in elaborazione automatica.",
        "done": "Aggiornamento completato: il piano è pronto.",
        "failed": (
            "L'elaborazione non è riuscita. Il presidio automatico recupererà gli snapshot mancanti alla prima finestra utile."
        ),
    }
    if status == "failed" and report.get("code") == "scheduler_disabled":
        messages["failed"] = (
            "L'aggiornamento non può essere elaborato perché la pianificazione del Piano del giorno è disattivata nelle impostazioni dello studio."
        )
    return {
        "ok": True,
        "job_id": str(job.get("id") or job_id),
        "stato": status,
        "tipo": str(job.get("job_type") or ""),
        "data": target_date,
        "creato_il": str(job.get("created_at") or ""),
        "iniziato_il": str(job.get("started_at") or ""),
        "concluso_il": str(job.get("finished_at") or ""),
        "messaggio": messages.get(status, "Stato dell'aggiornamento in verifica."),
        "report": {
            key: report[key]
            for key in (
                "ok",
                "mode",
                "target_date",
                "items_written",
                "users_planned",
                "signals_upserted",
                "automatic_recovery",
                "missing_snapshot_users",
            )
            if key in report
        },
    }


def apply_daily_plan_status_action(
    *,
    item_id: str,
    action: str,
    params: dict[str, Any],
    actor: str,
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Transizione diretta di stato (accetta/completa/delega/rinvia/rifiuta).

    Non tocca i dati di dominio: aggiorna solo lo stato dell'attività nel
    piano, con log idempotente e audit.
    """
    repo = repository_for_current_request()
    if idempotency_key:
        replay = repo.get_action_by_idempotency(idempotency_key)
        if replay is not None:
            return {**replay["result"], "replayed": True}

    new_status = STATUS_ACTIONS.get(action)
    if not new_status:
        raise ValueError(f"azione non riconosciuta: {action}")
    kwargs: dict[str, Any] = {}
    if action == "snooze":
        kwargs["snoozed_until"] = str(params.get("fino_a") or params.get("until") or "")
    if action == "reject":
        kwargs["note"] = str(params.get("motivo") or params.get("reason") or "")
    if action == "delegate":
        delegato = str(params.get("user_id") or "").strip()
        if not delegato:
            raise ValueError("indicare l'utente a cui delegare")
        kwargs["assigned_user_id"] = delegato

    item = repo.update_item_status(item_id, new_status, actor=actor, **kwargs)
    result = {"ok": True, "attivita": item_summary_payload(item)}
    repo.record_action(
        item_id=item_id,
        action=action,
        actor=actor,
        idempotency_key=idempotency_key,
        result=result,
    )
    return result


def create_daily_plan_domain_proposal(
    *, item_id: str, action: str, params: dict[str, Any], actor: str
) -> dict[str, Any]:
    """Crea una PROPOSTA approvabile nella coda Workflow Agents.

    L'esecuzione avviene solo dopo approvazione umana con permesso
    ``legal_skills.approva`` e flag di scrittura attivo — mai qui.
    """
    tool_name = DOMAIN_ACTIONS.get(action)
    if not tool_name:
        raise ValueError(f"azione applicativa non consentita: {action}")

    repo = repository_for_current_request()
    item = repo.get_item(item_id)
    if item is None:
        raise DailyPlanNotFound(item_id)

    from lex.agents.models import AgentPlan, AgentProposal, AgentRun, AgentStep
    from lex.agents.policies import required_permissions_for_tool, validate_client_payload
    from lex.agents.storage import WorkflowAgentStorage, current_tenant_scope

    validate_client_payload(params)

    titolo = str(params.get("titolo") or item.title)[:200]
    descrizione = str(
        params.get("descrizione")
        or f"{item.reason} (dal piano del giorno, priorità {item.priority})"
    )[:800]
    payload: dict[str, Any] = {
        "titolo": titolo,
        "descrizione": descrizione,
        "fascicolo_id": item.fascicolo_id,
    }
    if action == "create_deadline":
        payload["data_scadenza"] = str(params.get("data_scadenza") or item.due_at or "")
        payload["giorni_preavviso"] = [1]
    if action == "create_calendar_proposal":
        payload["descrizione"] = (
            "Proposta di agenda (da confermare manualmente in agenda): " + descrizione
        )[:800]
        payload["proposta_agenda"] = {
            "data_ora": str(params.get("data_ora") or item.scheduled_start or ""),
            "durata_minuti": int(item.estimated_minutes or 30),
        }
    if action == "create_pec_draft":
        payload = {
            "oggetto": titolo,
            "corpo": descrizione,
            "fascicolo_id": item.fascicolo_id,
            "send_blocked": True,
        }

    step = AgentStep(
        step_key=f"daily_plan_{action}",
        title=f"Piano del giorno: {titolo}"[:160],
        tool_name=tool_name,
        input_json=payload,
        mutates_state=True,
        approval_required=True,
        required_permissions=required_permissions_for_tool(tool_name, mutates_state=True),
        status="needs_approval",
        risk_level="low",
        baseline_minutes=15,
        review_minutes=2,
        correction_minutes=1,
    )
    plan = AgentPlan(
        workflow_code="daily_plan_action",
        title="Azione proposta dal piano del giorno",
        description="Proposta operativa generata dalla pagina Oggi: richiede approvazione.",
        steps=[step],
        fascicolo_id=item.fascicolo_id,
        risk_level="low",
        baseline_minutes=15,
        expected_review_minutes=2,
        expected_correction_minutes=1,
        confidence=float(item.confidence or 0.7),
    )
    tenant_scope = current_tenant_scope() or current_tenant_label()
    run = AgentRun(
        workflow_code="daily_plan_action",
        created_by=actor,
        plan=plan,
        tenant_scope=tenant_scope,
        fascicolo_id=item.fascicolo_id,
        status="needs_approval",
        risk_level="low",
        confidence=float(item.confidence or 0.7),
    )
    proposal = AgentProposal(
        run_id=run.id,
        step_id=step.id,
        tool_name=tool_name,
        title=step.title,
        payload=payload,
        action_type=tool_name,
        risk_level="low",
        editable_fields=("titolo", "descrizione", "data_scadenza", "note", "oggetto", "corpo"),
    )
    step.proposal_id = proposal.id
    run.proposals = [proposal]
    WorkflowAgentStorage().save_run(run)

    repo.record_action(
        item_id=item_id,
        action=action,
        actor=actor,
        result={"proposal_id": proposal.id, "run_id": run.id},
    )
    return {
        "ok": True,
        "proposta_creata": True,
        "proposal_id": proposal.id,
        "run_id": run.id,
        "messaggio": "Proposta inviata alla coda approvazioni: nessuna modifica è stata ancora applicata.",
    }


def daily_plan_error_payload(error: Exception) -> tuple[dict[str, Any], int]:
    if isinstance(error, DailyPlanForbidden):
        return {"ok": False, "code": "forbidden", "detail": "Operazione non autorizzata."}, 403
    if isinstance(error, DailyPlanRefreshJobNotFound):
        return {
            "ok": False,
            "code": "refresh_job_not_found",
            "detail": "Aggiornamento non trovato per questo studio.",
        }, 404
    if isinstance(error, (DailyPlanNotFound, KeyError)):
        return {"ok": False, "code": "not_found", "detail": "Attività non trovata."}, 404
    if isinstance(error, InvalidStatusTransition):
        return {
            "ok": False,
            "code": "invalid_transition",
            "detail": "La transizione di stato richiesta non è ammessa.",
        }, 409
    if isinstance(error, TenantMismatchError):
        return {"ok": False, "code": "tenant_mismatch", "detail": "Contesto studio non valido."}, 403
    if isinstance(error, ValueError):
        return {"ok": False, "code": "validation_error", "detail": str(error)[:200]}, 400
    return {
        "ok": False,
        "code": "daily_plan_internal_error",
        "detail": "Errore interno del piano del giorno.",
    }, 500


__all__ = [
    "DOMAIN_ACTIONS",
    "STATUS_ACTIONS",
    "apply_daily_plan_status_action",
    "build_react_daily_plan_payload",
    "create_daily_plan_domain_proposal",
    "daily_plan_backlog_payload",
    "daily_plan_coverage_payload",
    "daily_plan_error_payload",
    "daily_plan_item_detail_payload",
    "daily_plan_refresh_status_payload",
    "enqueue_daily_plan_refresh",
    "ITEM_STATUS_TRANSITIONS",
    "mark_daily_plan_refresh_scheduler_disabled",
]
