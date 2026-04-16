"""Runtime di osservabilita' applicativa."""

from __future__ import annotations

from time import monotonic
from typing import Any

from flask import Flask, current_app, g, has_app_context, request

from pct.runtime_metrics import RuntimeMetricsRegistry


def register_observability_runtime(app: Flask) -> RuntimeMetricsRegistry:
    """Registra metriche leggere del runtime Flask nel container web."""

    registry = RuntimeMetricsRegistry()
    app.extensions["runtime_metrics"] = registry

    @app.before_request
    def _runtime_metrics_before_request() -> None:
        g._request_started_monotonic = monotonic()

    @app.after_request
    def _runtime_metrics_after_request(response):
        started = getattr(g, "_request_started_monotonic", None)
        if started is not None:
            registry.observe_http(
                method=request.method,
                endpoint=_endpoint_bucket(),
                status_code=response.status_code,
                duration_ms=(monotonic() - started) * 1000,
            )
        return response

    return registry


def get_runtime_metrics_registry() -> RuntimeMetricsRegistry | None:
    if not has_app_context():
        return None
    return current_app.extensions.get("runtime_metrics")


def build_observability_payload(app: Flask | None = None) -> dict[str, Any]:
    runtime_app = app or current_app._get_current_object()
    registry: RuntimeMetricsRegistry | None = runtime_app.extensions.get("runtime_metrics")
    ocr_runtime = runtime_app.extensions.get("ocr_runtime")
    payload: dict[str, Any] = {
        "ok": True,
        "runtime": registry.snapshot() if registry is not None else {"http": {"buckets": []}, "lex": {}},
        "storage": {
            "default_mode": str(runtime_app.config.get("STORAGE_MODE_DEFAULT") or ("SQLITE" if runtime_app.config.get("SQLITE_MODE") else "JSON")),
            "sqlite_mode_default": bool(runtime_app.config.get("SQLITE_MODE")),
            "search_index": str(runtime_app.config.get("SEARCH_INDEX", "")),
        },
        "scheduler_worker_mode": bool(runtime_app.config.get("PCT_SCHEDULER_WORKER")),
        "ocr": ocr_runtime.status_snapshot() if ocr_runtime is not None else {"enabled": False},
        "providers": {},
    }

    try:
        from lex.providers.local_ai_service import get_local_ai_service

        payload["providers"]["local_ai"] = get_local_ai_service().monitoring_snapshot()
    except Exception as exc:
        payload["ok"] = False
        payload["providers"]["local_ai"] = {
            "runtime": {"status": "error"},
            "errore": str(exc),
        }

    return payload


def _endpoint_bucket() -> str:
    endpoint = (request.endpoint or request.path or "unknown").strip()
    if request.view_args:
        for key in sorted(request.view_args):
            value = str(request.view_args[key])
            if value:
                endpoint = endpoint.replace(value, f"<{key}>")
    return endpoint
