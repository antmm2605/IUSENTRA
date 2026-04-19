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
        "product": {
            "audit_events": 0,
            "authorization_surfaces": 0,
            "capabilities": [],
        },
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

    try:
        from pct.product_governance import (
            build_authorization_model_payload,
            build_observability_capabilities_payload,
        )
        from web.services.admin_surfaces_shared import get_auth_manager

        auth_stats = get_auth_manager().statistiche()
        auth_model = build_authorization_model_payload()
        capabilities = build_observability_capabilities_payload(
            audit_events=int(auth_stats.get("totale_eventi_audit", 0) or 0),
            runtime_ok=bool(payload.get("ok")),
        )
        payload["product"] = {
            "audit_events": int(auth_stats.get("totale_eventi_audit", 0) or 0),
            "authorization_surfaces": int(auth_model["summary"]["surfaces_total"]),
            "capabilities": capabilities["rows"],
        }
    except Exception:
        # Best effort: la diagnostica runtime deve restare disponibile anche senza la superficie prodotto.
        payload["product"] = payload.get("product") or {
            "audit_events": 0,
            "authorization_surfaces": 0,
            "capabilities": [],
        }

    payload["alerts"] = _build_observability_alerts(payload)
    errors = sum(1 for alert in payload["alerts"] if alert["severity"] == "danger")
    warnings = sum(1 for alert in payload["alerts"] if alert["severity"] == "warning")
    payload["summary"] = {
        "degraded": bool(payload["alerts"]),
        "status": "degraded" if payload["alerts"] else "ok",
        "status_label": "Degradi rilevati" if payload["alerts"] else "Nessun degrado rilevato",
        "errors": errors,
        "warnings": warnings,
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


def _build_observability_alerts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    http_buckets = list((payload.get("runtime") or {}).get("http", {}).get("buckets") or [])
    failing_buckets = [
        bucket
        for bucket in http_buckets
        if "[5" in str(bucket.get("bucket") or "") and int(bucket.get("count") or 0) > 0
    ]
    if failing_buckets:
        worst_bucket = max(failing_buckets, key=lambda item: int(item.get("count") or 0))
        alerts.append(
            {
                "severity": "danger",
                "title": "Endpoint con errori 5xx rilevati",
                "detail": (
                    f"Il bucket {worst_bucket.get('bucket')} ha registrato "
                    f"{int(worst_bucket.get('count') or 0)} risposte in errore."
                ),
                "remediation": (
                    "Controlla i log applicativi dell'endpoint indicato, verifica l'errore "
                    "a livello Flask e ripeti lo smoke test della superficie coinvolta."
                ),
            }
        )

    ocr = dict(payload.get("ocr") or {})
    if int(ocr.get("errori") or 0) > 0:
        alerts.append(
            {
                "severity": "warning",
                "title": "Pipeline OCR con errori pendenti",
                "detail": (
                    f"Risultano {int(ocr.get('errori') or 0)} job OCR falliti o da presidiare."
                ),
                "remediation": (
                    "Apri la salute sistema, individua i documenti falliti e rilancia "
                    "l'elaborazione solo dopo avere verificato file, Tesseract e storage."
                ),
            }
        )
    if int(ocr.get("in_coda") or 0) >= 20:
        alerts.append(
            {
                "severity": "warning",
                "title": "Coda OCR in accumulo",
                "detail": (
                    f"La coda OCR contiene {int(ocr.get('in_coda') or 0)} elementi in attesa."
                ),
                "remediation": (
                    "Verifica che il worker OCR sia vivo, che il database di coda non sia "
                    "bloccato e che il throughput dell'ultima ora non sia fermo."
                ),
            }
        )

    local_ai = dict((payload.get("providers") or {}).get("local_ai") or {})
    local_ai_runtime = dict(local_ai.get("runtime") or {})
    local_ai_status = str(local_ai_runtime.get("status") or "").strip().lower()
    local_ai_error = str(local_ai_runtime.get("last_error") or local_ai.get("errore") or "").strip()
    ai_enabled = bool((local_ai.get("settings") or {}).get("enabled", True))
    ai_online = bool(local_ai.get("runtime_online"))
    if ai_enabled and (local_ai_error or local_ai_status in {"error", "missing", "unsupported"} or not ai_online):
        alerts.append(
            {
                "severity": "danger",
                "title": "Runtime AI locale non operativo",
                "detail": local_ai_error
                or "Il provider locale non e' pronto oppure non risponde dal runtime applicativo.",
                "remediation": (
                    "Controlla la schermata impostazioni AI, verifica il runtime Ollama sullo "
                    "stesso host dell'app e riesegui il bootstrap prima di usare Lex o i motori assistiti."
                ),
            }
        )

    storage = dict(payload.get("storage") or {})
    if str(storage.get("default_mode") or "").upper() == "JSON":
        alerts.append(
            {
                "severity": "warning",
                "title": "Storage predefinito ancora su JSON",
                "detail": "Il runtime principale non sta ancora usando un backend SQL come default operativo.",
                "remediation": (
                    "Chiudi il percorso di migrazione sul tenant interessato e verifica la parity "
                    "read/write prima del cutover definitivo."
                ),
            }
        )

    product = dict(payload.get("product") or {})
    if not list(product.get("capabilities") or []):
        alerts.append(
            {
                "severity": "warning",
                "title": "Capability di prodotto non disponibili",
                "detail": "La lettura prodotto non ha restituito capability operative o superfici autorizzative.",
                "remediation": (
                    "Controlla audit, bootstrap admin e servizi di governance: la diagnostica deve "
                    "raccontare sia il runtime sia il prodotto, non solo i log tecnici."
                ),
            }
        )

    return alerts
