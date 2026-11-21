"""Bridge React per Lex Workflow Agents."""

from __future__ import annotations

from typing import Any, Iterable

from flask import current_app

from lex.agents import WorkflowAgentRuntime
from lex.agents.policies import WorkflowAgentPolicyError
from lex.agents.serialization import public_dict
from lex.agents.storage import WorkflowAgentStorage, current_tenant_scope
from web.services.feature_flags import is_feature_enabled


WORKFLOW_AGENT_PERMISSIONS = (
    "ai.usa",
    "legal_skills.leggi",
    "legal_skills.esegui",
    "legal_skills.approva",
    "agenda.leggi",
    "agenda.scrivi",
    "scadenziario.leggi",
    "scadenziario.scrivi",
    "fascicoli.leggi",
    "fascicoli.scrivi",
    "clienti.scrivi",
    "messaggi.scrivi",
    "fatturazione.leggi",
    "fatturazione.scrivi",
    "telematico.leggi",
    "telematico.valida",
)


def _runtime(tenant_scope: str | None = None) -> WorkflowAgentRuntime:
    return WorkflowAgentRuntime(storage=WorkflowAgentStorage(tenant_scope=tenant_scope))


def workflow_agent_flags_payload() -> dict[str, bool]:
    config = current_app.config
    return {
        "enabled": is_feature_enabled("lex.workflowAgents.enabled", config),
        "writeActions": is_feature_enabled("lex.workflowAgents.writeActions", config),
        "scheduledRuns": is_feature_enabled("lex.workflowAgents.scheduledRuns", config),
        "homeRoute": is_feature_enabled("routes.appV2.workflowAgents.home", config),
        "reviewQueueRoute": is_feature_enabled("routes.appV2.workflowAgents.reviewQueue", config),
    }


def _presidio_mattutino() -> dict[str, Any]:
    """Il presidio automatico di ogni mattina è il «Piano del giorno» dello scheduler: ultimo giro ed esito."""
    try:
        from pct.scheduler_registry import scheduler_registry_repository

        repo = scheduler_registry_repository(dict(current_app.config))
        lavoro = repo.get_job("studio_daily_operational_plan") or {}
        giro = repo.latest_runs_by_job().get("studio_daily_operational_plan") or {}
    except Exception:
        return {}
    if not lavoro:
        return {}
    esiti = {"completed": "Completato", "failed": "Non riuscito", "cancelled": "Annullato", "missed": "Saltato",
             "running": "In corso"}
    return {"titolo": "Oggi (piano del giorno)", "attivo": bool(lavoro.get("enabled")),
            "pianificazione": str(lavoro.get("schedule_label") or ""), "href": "/oggi",
            "ultimo_giro": {"data": str(giro.get("finished_at") or giro.get("started_at") or ""),
                            "esito": esiti.get(str(giro.get("status") or ""), str(giro.get("status") or "")),
                            "messaggio": str(giro.get("error") or "").strip()} if giro else {}}


def build_workflow_agents_payload() -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    runtime = _runtime(tenant_scope)
    try:
        # Le anteprime vecchie e senza fascicolo non restano aperte per sempre nella coda (collaudo 21/11).
        runtime.chiudi_proposte_superate()
    except Exception:
        current_app.logger.exception("Lavori automatici di Lex: chiusura delle proposte superate non riuscita")
    return {
        "ok": True,
        "feature_flags": workflow_agent_flags_payload(),
        "workflows": runtime.list_workflows(),
        "latest_runs": runtime.latest_runs(limit=8),
        "ultimi_giri": runtime.ultimi_giri_per_lavoro(),
        "presidio_mattutino": _presidio_mattutino(),
        "metrics": runtime.metrics_summary(),
    }


def preview_workflow_agent(payload: dict[str, Any], *, actor: str, user_permissions: Iterable[str]) -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    run = _runtime(tenant_scope).preview(payload, actor=actor, tenant_scope=tenant_scope, user_permissions=user_permissions)
    return {"ok": True, "run": public_dict(run)}


def get_workflow_agent_run(run_id: str) -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    run = _runtime(tenant_scope).get_run(run_id)
    return {"ok": True, "run": public_dict(run)}


def list_workflow_agent_approvals() -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    return {"ok": True, "approvals": _runtime(tenant_scope).list_approvals()}


def approve_workflow_agent_run(payload: dict[str, Any], *, run_id: str, actor: str, user_permissions: Iterable[str]) -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    write_enabled = is_feature_enabled("lex.workflowAgents.writeActions", current_app.config)
    run = _runtime(tenant_scope).approve(
        run_id,
        payload,
        actor=actor,
        tenant_scope=tenant_scope,
        write_feature_enabled=write_enabled,
        user_permissions=user_permissions,
    )
    return {"ok": True, "run": public_dict(run)}


def reject_workflow_agent_run(payload: dict[str, Any], *, run_id: str, actor: str) -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    run = _runtime(tenant_scope).reject(run_id, payload, actor=actor)
    return {"ok": True, "run": public_dict(run)}


def workflow_agent_metrics_payload() -> dict[str, Any]:
    tenant_scope = current_tenant_scope()
    return {"ok": True, "metrics": _runtime(tenant_scope).metrics_summary()}


def workflow_agent_error_payload(error: Exception) -> tuple[dict[str, Any], int]:
    if isinstance(error, WorkflowAgentPolicyError):
        return {"ok": False, "code": error.code, "message": error.public_message}, error.status_code
    if isinstance(error, KeyError):
        return {"ok": False, "code": "not_found", "message": "Percorso agentico non trovato."}, 404
    if isinstance(error, PermissionError):
        return {"ok": False, "code": "tenant_forbidden", "message": "Percorso non disponibile per questo studio."}, 403
    return {"ok": False, "code": "workflow_agent_error", "message": "Operazione agentica non completata."}, 500
