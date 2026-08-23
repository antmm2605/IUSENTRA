"""Payload read-only del Data Consistency Center React."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pct.data_consistency import build_sql_consistency_snapshot


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def build_data_consistency_payload(*, studio_db: Any, tenant_slug: str = "") -> dict[str, Any]:
    """Costruisce un payload aggregato senza esporre record, path o mirror."""

    snapshot = build_sql_consistency_snapshot(studio_db)
    warnings: list[dict[str, str]] = []
    if not snapshot["ok"]:
        warnings.append(
            {
                "code": "lettura_sql_incompleta",
                "message": "Almeno un dominio SQL non è leggibile: nessun mirror JSON è stato usato come sostituto.",
            }
        )
    return {
        "ok": bool(snapshot["ok"]),
        "generatedAt": _iso_now(),
        "sourceOfTruth": snapshot["source_of_truth"],
        "tenantScope": str(tenant_slug or "studio corrente"),
        "contracts": snapshot["contracts"],
        "domains": snapshot["domains"],
        "outbox": snapshot["outbox"],
        "warnings": warnings,
    }


def build_data_consistency_error_payload(message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "generatedAt": _iso_now(),
        "sourceOfTruth": "sql",
        "tenantScope": "",
        "contracts": {"writes": "none", "json_scanned": False, "fallback_used": False, "source_of_truth": "sql"},
        "domains": [],
        "outbox": {"pending": 0, "processed": 0, "failed": 0, "total": 0, "readable": False},
        "warnings": [{"code": "consistenza_dati_errore_controllato", "message": message}],
    }
