"""Dashboard salute sistema per admin e superadmin."""

from __future__ import annotations

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

