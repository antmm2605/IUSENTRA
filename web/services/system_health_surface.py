"""Dashboard salute sistema per admin e superadmin."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import current_app

from web.services.observability_runtime import build_observability_payload
from web.services.admin_surfaces_shared import get_backup_manager
from web.services.server_maintenance_surface import build_server_maintenance_surface


def _fmt_mb(size_bytes: int) -> str:
    return f"{(int(size_bytes or 0) / (1024 * 1024)):.1f} MB"


def _slow_endpoint_action(bucket: dict[str, Any] | None) -> dict[str, str]:
    if not bucket:
        return {
            "title": "Nessuna latenza misurata",
            "detail": "Eseguire un flusso reale per popolare la tabella endpoint.",
            "action": "Apri osservabilità dopo un uso reale del sistema.",
        }
    label = str(bucket.get("bucket") or "")
    if "server_maintenance_admin" in label:
        return {
            "title": "Manutenzione server lenta",
            "detail": "La scansione o la compattazione storage è pesante: usare azioni mirate e leggere il dettaglio disco.",
            "action": "Apri Server e manutenzione e controlla backup, normativa globale, Docker e log.",
        }
    if "assistente" in label or "Lex" in label:
        return {
            "title": "Risposta Lex lenta",
            "detail": "Misurare primo token, fonti usate e dimensione del contesto fascicolo.",
            "action": "Apri Scorecard Lex e verifica run reali, fonti utili e casi falliti.",
        }
    return {
        "title": "Endpoint lento",
        "detail": label,
        "action": "Controllare log applicativi e ripetere il flusso con un singolo caso reale.",
    }


def build_system_health_surface() -> dict:
    observability = build_observability_payload(current_app._get_current_object())
    maintenance = build_server_maintenance_surface()
    backup_manager = get_backup_manager()
    backup_last = backup_manager.ultimo()

    runtime = dict(observability.get("runtime") or {})
    http_buckets = list((runtime.get("http") or {}).get("buckets") or [])
    slowest = http_buckets[0] if http_buckets else None
    lex_first_token = dict((runtime.get("lex") or {}).get("first_token") or {})
    ocr = dict(observability.get("ocr") or {})
    local_ai = dict((observability.get("providers") or {}).get("local_ai") or {})
    advanced_ai = dict((observability.get("providers") or {}).get("advanced_ai") or {})
    advanced_enabled = list(advanced_ai.get("enabled") or [])
    advanced_to_measure = list(advanced_ai.get("to_measure") or [])
    storage_summary = dict(maintenance.get("summary") or {})
    host_console = dict(maintenance.get("host_console") or {})
    disk = dict(maintenance.get("disk") or {})

    cards = [
        {
            "label": "Latenza media endpoint",
            "value": f"{slowest['avg_ms']:.0f} ms" if slowest else "n.d.",
            "detail": slowest["bucket"] if slowest else "Nessun campione HTTP disponibile",
        },
        {
            "label": "Primo token Lex",
            "value": f"{lex_first_token.get('avg_ms', 0):.0f} ms" if lex_first_token.get("count") else "n.d.",
            "detail": f"campioni {lex_first_token.get('count', 0)}",
        },
        {
            "label": "Coda OCR",
            "value": str(ocr.get("queue_depth", 0) or 0),
            "detail": f"worker {ocr.get('workers', 0) or 0} · throughput {ocr.get('completed', 0) or 0}",
        },
        {
            "label": "Provider AI",
            "value": str(((local_ai.get("runtime") or {}).get("status_text") or (local_ai.get("runtime") or {}).get("status") or "n.d.")),
            "detail": str(((local_ai.get("resolved_models") or {}).get("chat") or "modello non risolto")),
        },
        {
            "label": "AI avanzata",
            "value": str(len(advanced_enabled)),
            "detail": f"{len(advanced_to_measure)} capacita' da misurare",
        },
        {
            "label": "Disco server",
            "value": disk.get("used_label") or observability.get("storage", {}).get("disk_used_label") or "n.d.",
            "detail": f"liberi {disk.get('free_label') or observability.get('storage', {}).get('disk_free_label') or 'n.d.'} su {disk.get('total_label') or observability.get('storage', {}).get('disk_total_label') or 'n.d.'}",
        },
        {
            "label": "Studi attivi",
            "value": storage_summary.get("tenant_total_size_label") or "n.d.",
            "detail": f"{storage_summary.get('tenant_count', 0)} studi · backup {storage_summary.get('tenant_backup_size_label') or 'n.d.'}",
        },
        {
            "label": "Sistema e piattaforma",
            "value": host_console.get("outside_tenants_label") or "n.d.",
            "detail": host_console.get("outside_tenants_note") or "Docker, codice deploy, fonti globali e sistema operativo.",
        },
        {
            "label": "Ultimo backup",
            "value": getattr(backup_last, "timestamp", "")[:19] or "mai",
            "detail": getattr(backup_last, "esito", "nessun esito registrato") if backup_last else "nessun backup registrato",
        },
    ]
    storage_rows = [
        {
            "label": "Studi attivi",
            "value": storage_summary.get("tenant_total_size_label") or "n.d.",
            "detail": f"{storage_summary.get('tenant_count', 0)} studi registrati, {storage_summary.get('inactive_tenant_dirs', 0)} cartelle escluse.",
        },
        {
            "label": "Posta e allegati studi",
            "value": storage_summary.get("tenant_email_size_label") or "n.d.",
            "detail": "PEC, email ordinaria, EML e allegati tenant-aware.",
        },
        {
            "label": "Backup e mirror studi",
            "value": storage_summary.get("tenant_backup_size_label") or "n.d.",
            "detail": "Retention: una sola copia completa per studio; temporanei e mirror sono pulibili.",
        },
        {
            "label": "Sistema e piattaforma",
            "value": host_console.get("outside_tenants_label") or "n.d.",
            "detail": host_console.get("outside_tenants_note") or "",
        },
    ]

    return {
        "cards": cards,
        "http_buckets": http_buckets[:8],
        "slow_endpoint_action": _slow_endpoint_action(slowest),
        "storage": {
            "disk": disk,
            "summary": storage_summary,
            "host_console": host_console,
            "rows": storage_rows,
            "actions": [
                {"label": "Apri Server e manutenzione", "href": "/admin/server-manutenzione"},
                {"label": "Apri Osservabilità runtime", "href": "/admin/osservabilita"},
            ],
        },
        "lex_first_token": lex_first_token,
        "ocr": ocr,
        "local_ai": local_ai,
        "advanced_ai": advanced_ai,
        "scheduler_worker_mode": bool(observability.get("scheduler_worker_mode")),
    }


def _status_from_alerts(alerts: list[dict[str, Any]], *, codes: set[str]) -> str:
    matched = [
        alert
        for alert in alerts
        if str(alert.get("normalized_code") or alert.get("code") or "") in codes
    ]
    if any(str(alert.get("severity") or "") == "danger" for alert in matched):
        return "error"
    if matched:
        return "degraded"
    return "ok"


def build_system_health_api_payload() -> dict[str, Any]:
    observability = build_observability_payload(current_app._get_current_object())
    alerts = list(observability.get("alerts") or [])
    storage = dict(observability.get("storage") or {})
    scheduler_status = "ok"
    ocr_status = _status_from_alerts(
        alerts,
        codes={"OCR_TIMEOUT", "OCR_QUEUE_OVERFLOW", "OCR_WORKER_STALLED"},
    )
    ai_status = _status_from_alerts(alerts, codes={"AI_MODEL_UNAVAILABLE"})
    db_status = _status_from_alerts(alerts, codes={"TENANT_DB_ERROR", "MIGRATION_FAILED"})
    if db_status == "ok" and str(storage.get("default_mode") or "").upper() not in {"SQLITE", "POSTGRESQL"}:
        db_status = "degraded"

    overall_status = "ok"
    if "error" in {ocr_status, ai_status, db_status}:
        overall_status = "error"
    elif "degraded" in {ocr_status, ai_status, db_status} or bool(alerts):
        overall_status = "degraded"

    return {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "status": overall_status,
        "scheduler": scheduler_status,
        "ocr": ocr_status,
        "ai": ai_status,
        "db": db_status,
        "components": {
            "scheduler": {
                "status": scheduler_status,
                "detail": "Worker dedicato attivo" if observability.get("scheduler_worker_mode") else "Modalità web",
            },
            "ocr": {
                "status": ocr_status,
                "detail": f"Coda {int((observability.get('ocr') or {}).get('in_coda') or 0)} · throughput {int((observability.get('ocr') or {}).get('throughput_ultima_ora') or 0)}",
            },
            "ai": {
                "status": ai_status,
                "detail": str((((observability.get("providers") or {}).get("local_ai") or {}).get("runtime") or {}).get("status") or "n.d."),
            },
            "db": {
                "status": db_status,
                "detail": f"Backend predefinito {str(storage.get('default_mode') or 'n.d.')}",
            },
        },
        "alerts": alerts,
        "actions_required": [
            {
                "code": str(alert.get("normalized_code") or alert.get("code") or ""),
                "title": str(alert.get("title") or ""),
                "message": str(alert.get("operator_message") or ""),
                "action": str(alert.get("remediation") or ""),
            }
            for alert in alerts
        ],
        "error_taxonomy": dict(observability.get("error_taxonomy") or {}),
    }
