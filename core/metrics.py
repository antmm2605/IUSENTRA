"""Esportatore Prometheus testuale senza dati sensibili."""

from __future__ import annotations

from typing import Any


def prometheus_payload(observability: dict[str, Any]) -> str:
    lines = [
        "# HELP iusentra_health_status Stato runtime 1=ok 0=degraded",
        "# TYPE iusentra_health_status gauge",
    ]
    summary = dict(observability.get("summary") or {})
    lines.append(f"iusentra_health_status {0 if summary.get('degraded') else 1}")
    runtime = dict(observability.get("runtime") or {})
    for bucket in list(dict(runtime.get("http") or {}).get("buckets") or []):
        label = _safe_label(str(bucket.get("bucket") or "unknown"))
        lines.append(f'iusentra_http_requests_total{{bucket="{label}"}} {int(bucket.get("count") or 0)}')
        lines.append(f'iusentra_http_request_avg_ms{{bucket="{label}"}} {float(bucket.get("avg_ms") or 0)}')
        lines.append(f'iusentra_http_request_p95_ms{{bucket="{label}"}} {float(bucket.get("p95_ms") or 0)}')
    ocr = dict(observability.get("ocr") or {})
    # ``OCRJobStore.status_snapshot`` espone le chiavi italiane usate dal
    # pannello operativo. Manteniamo anche gli alias storici inglesi per i
    # payload esterni, senza pubblicare uno zero fittizio quando esistono job
    # da presidiare.
    def first_count(*keys: str) -> int:
        for key in keys:
            if key in ocr and ocr[key] is not None:
                return int(ocr[key])
        return 0

    lines.append(f"iusentra_ocr_queue_pending {first_count('in_coda', 'pending', 'pending_jobs')}")
    lines.append(f"iusentra_ocr_jobs_failed {first_count('errori', 'failed', 'failed_jobs')}")
    alerts = list(observability.get("alerts") or [])
    lines.append(f"iusentra_alerts_total {len(alerts)}")
    return "\n".join(lines) + "\n"


def _safe_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', "'")[:160]
