"""Superficie admin per governance prodotto: storage, policy, migrazione e audit."""

from __future__ import annotations

from typing import Any

from flask import current_app

from pct.product_governance import (
    build_authorization_model_payload,
    build_e2e_flow_payload,
    build_migration_program_payload,
    build_observability_capabilities_payload,
    build_storage_parity_payload,
)
from web.services.admin_surfaces_shared import get_auth_manager
from web.services.observability_runtime import build_observability_payload


def build_product_governance_surface() -> dict[str, Any]:
    auth_manager = get_auth_manager()
    auth_stats = auth_manager.statistiche()
    recent_audit = [evento.to_dict() for evento in auth_manager.audit_log(limit=8)]
    observability = build_observability_payload(current_app._get_current_object())
    storage = build_storage_parity_payload()
    authorization = build_authorization_model_payload()
    migration = build_migration_program_payload()
    e2e = build_e2e_flow_payload()
    observability_product = build_observability_capabilities_payload(
        audit_events=int(auth_stats.get("totale_eventi_audit", 0) or 0),
        runtime_ok=bool(observability.get("ok")),
    )

    return {
        "headline": {
            "storage_domains": storage["summary"]["domains_total"],
            "postgres_rw_ready": storage["summary"]["postgres_rw_ready"],
            "authorization_surfaces": authorization["summary"]["surfaces_total"],
            "e2e_flows": e2e["summary"]["flows_total"],
            "audit_events": int(auth_stats.get("totale_eventi_audit", 0) or 0),
        },
        "runtime": {
            "storage_default_mode": str((observability.get("storage") or {}).get("default_mode") or ""),
            "scheduler_worker_mode": bool(observability.get("scheduler_worker_mode")),
            "ocr_enabled": bool((observability.get("ocr") or {}).get("enabled")),
            "local_ai_status": str((((observability.get("providers") or {}).get("local_ai") or {}).get("runtime") or {}).get("status") or "n.d."),
        },
        "storage": storage,
        "authorization": authorization,
        "migration": migration,
        "e2e": e2e,
        "observability": observability_product,
        "recent_audit": recent_audit,
    }

