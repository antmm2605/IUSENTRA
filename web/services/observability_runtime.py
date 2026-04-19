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
        "thresholds": _build_observability_thresholds(),
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
    payload["taxonomy"] = {
        "families": sorted({str(alert.get("family") or "") for alert in payload["alerts"] if alert.get("family")}),
        "components": sorted({str(alert.get("component") or "") for alert in payload["alerts"] if alert.get("component")}),
    }
    payload["summary"] = {
        "degraded": bool(payload["alerts"]),
        "status": "degraded" if payload["alerts"] else "ok",
        "status_label": "Degradi rilevati" if payload["alerts"] else "Nessun degrado rilevato",
        "errors": errors,
        "warnings": warnings,
    }

    return payload


def _build_observability_thresholds() -> dict[str, Any]:
    return {
        "http_5xx_bucket": {"label": "Almeno 1 risposta 5xx nello stesso bucket endpoint", "limit": 1},
        "ocr_error_jobs": {"label": "Almeno 1 job OCR fallito", "limit": 1},
        "ocr_queue_backlog": {"label": "Coda OCR in warning da 20 elementi", "limit": 20},
        "ocr_worker_stall": {"label": "Coda OCR > 0 e throughput ultima ora = 0", "limit": 1},
        "local_ai_runtime": {"label": "Runtime AI locale deve risultare online quando e' abilitato", "required": True},
        "storage_default_mode": {"label": "Il backend predefinito non deve restare JSON in produzione", "allowed": ("SQLITE", "POSTGRESQL")},
    }


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
    thresholds = dict(payload.get("thresholds") or {})

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
                "family": "HTTP",
                "component": "Runtime Flask",
                "code": "HTTP_5XX_BUCKET",
                "title": "Endpoint con errori 5xx rilevati",
                "detail": (
                    f"Il bucket {worst_bucket.get('bucket')} ha registrato "
                    f"{int(worst_bucket.get('count') or 0)} risposte in errore."
                ),
                "threshold": str((thresholds.get("http_5xx_bucket") or {}).get("label") or ""),
                "remediation": (
                    "Controlla i log applicativi dell'endpoint indicato, verifica l'errore "
                    "a livello Flask e ripeti lo smoke test della superficie coinvolta."
                ),
                "remediation_steps": [
                    "Apri i log applicativi e identifica l'eccezione reale del bucket indicato.",
                    "Ripeti lo smoke test della route coinvolta con sessione autenticata o payload reale.",
                    "Verifica che la superficie correlata non abbia regressioni su template, servizio o storage.",
                ],
            }
        )

    ocr = dict(payload.get("ocr") or {})
    if int(ocr.get("errori") or 0) > 0:
        alerts.append(
            {
                "severity": "warning",
                "family": "OCR",
                "component": "Pipeline OCR",
                "code": "OCR_FAILED_JOBS",
                "title": "Pipeline OCR con errori pendenti",
                "detail": (
                    f"Risultano {int(ocr.get('errori') or 0)} job OCR falliti o da presidiare."
                ),
                "threshold": str((thresholds.get("ocr_error_jobs") or {}).get("label") or ""),
                "remediation": (
                    "Apri la salute sistema, individua i documenti falliti e rilancia "
                    "l'elaborazione solo dopo avere verificato file, Tesseract e storage."
                ),
                "remediation_steps": [
                    "Individua i documenti OCR falliti e verifica che i file siano leggibili.",
                    "Controlla Tesseract, dipendenze OCR e spazio disco del tenant.",
                    "Rilancia i job solo dopo il ripristino del runtime OCR.",
                ],
            }
        )
    if int(ocr.get("in_coda") or 0) >= 20:
        alerts.append(
            {
                "severity": "warning",
                "family": "OCR",
                "component": "Pipeline OCR",
                "code": "OCR_QUEUE_BACKLOG",
                "title": "Coda OCR in accumulo",
                "detail": (
                    f"La coda OCR contiene {int(ocr.get('in_coda') or 0)} elementi in attesa."
                ),
                "threshold": str((thresholds.get("ocr_queue_backlog") or {}).get("label") or ""),
                "remediation": (
                    "Verifica che il worker OCR sia vivo, che il database di coda non sia "
                    "bloccato e che il throughput dell'ultima ora non sia fermo."
                ),
                "remediation_steps": [
                    "Controlla che il worker OCR sia in esecuzione e non sia bloccato.",
                    "Verifica il throughput dell'ultima ora e lo stato della coda.",
                    "Se la coda non cala, riavvia il worker e riprendi il monitoraggio.",
                ],
            }
        )
    if int(ocr.get("in_coda") or 0) > 0 and int(ocr.get("throughput_ultima_ora") or 0) == 0:
        alerts.append(
            {
                "severity": "danger",
                "family": "WORKER",
                "component": "Worker OCR",
                "code": "OCR_WORKER_STALLED",
                "title": "Worker OCR fermo con coda aperta",
                "detail": (
                    f"La coda OCR ha {int(ocr.get('in_coda') or 0)} elementi ma il throughput dell'ultima ora e' zero."
                ),
                "threshold": str((thresholds.get("ocr_worker_stall") or {}).get("label") or ""),
                "remediation": (
                    "Il worker OCR sembra fermo: verifica processo, log del worker e lock sul database di coda."
                ),
                "remediation_steps": [
                    "Apri i log del worker OCR e cerca eccezioni o riavvii falliti.",
                    "Verifica che il database di coda non sia in lock e che il filesystem tenant sia accessibile.",
                    "Riavvia il worker OCR e conferma che il throughput torni a salire.",
                ],
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
                "family": "AI",
                "component": "Runtime AI locale",
                "code": "LOCAL_AI_RUNTIME_DOWN",
                "title": "Runtime AI locale non operativo",
                "detail": local_ai_error
                or "Il provider locale non e' pronto oppure non risponde dal runtime applicativo.",
                "threshold": str((thresholds.get("local_ai_runtime") or {}).get("label") or ""),
                "remediation": (
                    "Controlla la schermata impostazioni AI, verifica il runtime Ollama sullo "
                    "stesso host dell'app e riesegui il bootstrap prima di usare Lex o i motori assistiti."
                ),
                "remediation_steps": [
                    "Verifica che Ollama o il provider locale sia realmente avviato sullo stesso host dell'app.",
                    "Controlla modello, porta e URL del runtime AI configurato.",
                    "Riesegui il bootstrap AI e riprova prima di usare Lex o Coverage AI.",
                ],
            }
        )

    storage = dict(payload.get("storage") or {})
    if str(storage.get("default_mode") or "").upper() == "JSON":
        alerts.append(
            {
                "severity": "warning",
                "family": "STORAGE",
                "component": "Backend strutturato",
                "code": "STORAGE_DEFAULT_JSON",
                "title": "Storage predefinito ancora su JSON",
                "detail": "Il runtime principale non sta ancora usando un backend SQL come default operativo.",
                "threshold": str((thresholds.get("storage_default_mode") or {}).get("label") or ""),
                "remediation": (
                    "Chiudi il percorso di migrazione sul tenant interessato e verifica la parity "
                    "read/write prima del cutover definitivo."
                ),
                "remediation_steps": [
                    "Verifica selected_mode ed effective_runtime_kind del tenant coinvolto.",
                    "Chiudi la migrazione tenant-aware e riesegui il check di parity read/write.",
                    "Conferma che il backend effettivo non sia piu' JSON nella governance prodotto.",
                ],
            }
        )

    product = dict(payload.get("product") or {})
    if not list(product.get("capabilities") or []):
        alerts.append(
            {
                "severity": "warning",
                "family": "PRODUCT",
                "component": "Governance prodotto",
                "code": "PRODUCT_CAPABILITY_GAP",
                "title": "Capability di prodotto non disponibili",
                "detail": "La lettura prodotto non ha restituito capability operative o superfici autorizzative.",
                "threshold": "Le capability di prodotto devono essere presenti e leggibili nella diagnostica runtime.",
                "remediation": (
                    "Controlla audit, bootstrap admin e servizi di governance: la diagnostica deve "
                    "raccontare sia il runtime sia il prodotto, non solo i log tecnici."
                ),
                "remediation_steps": [
                    "Verifica bootstrap admin, audit log e servizi di governance.",
                    "Controlla che la superficie observability riesca a leggere capability e autorizzazioni.",
                    "Ripeti il controllo dopo il ripristino del wiring admin.",
                ],
            }
        )

    return alerts
