"""Dashboard salute sistema per admin e superadmin."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import current_app

from web.services.admin_surfaces_shared import (
    get_backup_manager,
    path_size_bytes,
)
from web.services.observability_runtime import build_observability_payload


def _fmt_mb(size_bytes: int) -> str:
    return f"{(int(size_bytes or 0) / (1024 * 1024)):.1f} MB"


def build_system_health_surface() -> dict:
    observability = build_observability_payload(current_app._get_current_object())
    backup_manager = get_backup_manager()
    backup_last = backup_manager.ultimo()

    runtime = dict(observability.get("runtime") or {})
    http_buckets = list((runtime.get("http") or {}).get("buckets") or [])
    lex_first_token = dict((runtime.get("lex") or {}).get("first_token") or {})
    ocr = dict(observability.get("ocr") or {})
    local_ai = dict((observability.get("providers") or {}).get("local_ai") or {})

    cards = [
        {
            "label": "Latenza media endpoint",
            "value": f"{http_buckets[0]['avg_ms']:.0f} ms" if http_buckets else "n.d.",
            "detail": http_buckets[0]["bucket"] if http_buckets else "Nessun campione HTTP disponibile",
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
            "label": "Spazio dati",
            "value": _fmt_mb(path_size_bytes(str(current_app.config.get("CLIENTI_DB", "")))),
            "detail": "stima area dati principale",
        },
        {
            "label": "Ultimo backup",
            "value": getattr(backup_last, "timestamp", "")[:19] or "mai",
            "detail": getattr(backup_last, "esito", "nessun esito registrato") if backup_last else "nessun backup registrato",
        },
    ]

    return {
        "cards": cards,
        "http_buckets": http_buckets[:8],
        "lex_first_token": lex_first_token,
        "ocr": ocr,
        "local_ai": local_ai,
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
                "detail": "Worker dedicato attivo" if observability.get("scheduler_worker_mode") else "Modalita web",
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
