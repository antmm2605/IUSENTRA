"""Runtime automatico per i presidi fascicoli.

Questo modulo coordina i presidi che devono girare fuori dalla richiesta UI:
lettura documentale/economica, consolidamento pagamenti e stato pratica.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, g, has_request_context, session


def _text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _attach_tenant_context(manager: Any, studio: Any) -> None:
    slug = _text(getattr(studio, "slug", "")).lower()
    g.multi_tenant_enabled = True
    g.tenant = studio
    g.tenant_context_slug = slug
    g.tenant_context_required = False
    g.tenant_context_missing = False
    g.data_paths = manager.percorsi_dati(slug, reconcile_aliases=False, ensure_baseline=False)
    try:
        from web.services.storage_runtime import get_request_storage_runtime

        g.storage_runtime = get_request_storage_runtime(g.data_paths["CLIENTI_DB"]).to_dict()
    except Exception:
        g.storage_runtime = None
    if has_request_context():
        session["tenant_slug"] = slug


def _active_tenants(app: Flask) -> list[Any]:
    if not app.config.get("MULTI_TENANT"):
        return []
    try:
        from pct.tenant import GestioneTenant, StatoTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        return [
            studio
            for studio in manager.lista()
            if getattr(studio, "stato", "") != StatoTenant.SOSPESO
        ]
    except Exception:
        return []


def run_fascicoli_document_economic_presidio_for_current_context(
    *,
    limit: int = 25,
    actor: str = "IUSENTRA automatico",
) -> dict[str, Any]:
    """Esegue il presidio sul tenant già presente in `g`.

    La funzione è usabile sia da API autenticata sia da scheduler con contesto
    tenant preparato dal runtime.
    """

    from web.helpers import get_fascicoli, get_fatturazione
    from web.services.react_dashboard_cache import clear_dashboard_payload_cache
    from web.services.react_fascicoli_bridge import run_react_fascicoli_economic_presidio
    from web.services.react_fascicoli_cache import clear_react_fascicoli_list_cache

    report = run_react_fascicoli_economic_presidio(
        get_fascicoli=get_fascicoli,
        get_fatturazione=get_fatturazione,
        actor=actor,
        limit=max(1, int(limit or 25)),
    )
    if any(
        int(report.get(key) or 0)
        for key in (
            "createdCount",
            "contributiUpdatedCount",
            "documentAnalysisUpdatedCount",
            "statusDefinedUpdatedCount",
        )
    ):
        clear_dashboard_payload_cache()
        clear_react_fascicoli_list_cache()
    return report


def run_fascicoli_document_economic_presidio_for_all_tenants(
    app: Flask,
    *,
    limit_per_tenant: int = 25,
    actor: str = "IUSENTRA scheduler",
) -> dict[str, Any]:
    """Esegue il presidio automatico su tutti gli studi attivi.

    Usa un request context interno per rispettare le stesse regole tenant-aware
    delle API React, senza leggere dati cross-studio e senza fallback JSON come
    fonte decisionale.
    """

    totals = {
        "createdCount": 0,
        "existingCount": 0,
        "missingBasisCount": 0,
        "processedDefined": 0,
        "contributiCheckedCount": 0,
        "contributiUpdatedCount": 0,
        "contributiMissingCount": 0,
        "documentAnalysisUpdatedCount": 0,
        "documentAnalysisCandidateCount": 0,
        "documentAnalysisPendingCount": 0,
        "statusDefinedUpdatedCount": 0,
        "skippedCount": 0,
    }
    tenants: list[dict[str, Any]] = []
    active = _active_tenants(app)
    if active:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in active:
            slug = _text(getattr(studio, "slug", "")).lower()
            with app.test_request_context(f"/__scheduler/fascicoli-presidi/{slug}"):
                _attach_tenant_context(manager, studio)
                report = run_fascicoli_document_economic_presidio_for_current_context(
                    limit=limit_per_tenant,
                    actor=actor,
                )
            tenant_report = {"tenant": slug, **report}
            tenants.append(tenant_report)
            for key in totals:
                totals[key] += int(report.get(key) or 0)
    elif app.config.get("MULTI_TENANT"):
        # Studio multi-tenant senza studi attivi: non si ripiega sul contesto
        # "default", che leggerebbe percorsi non appartenenti ad alcuno studio.
        # Il presidio dichiara il guasto invece di riportare un lavoro non fatto.
        return {
            "ok": False,
            "job": "fascicoli_document_economic_presidio",
            "error": "nessuno studio attivo: il presidio non ha fascicoli su cui lavorare",
            "source_of_truth": "registro studi del worker scheduler",
            "tenants": [],
            "totals": totals,
        }
    else:
        with app.test_request_context("/__scheduler/fascicoli-presidi/default"):
            g.multi_tenant_enabled = False
            g.tenant_context_missing = False
            g.tenant_context_slug = ""
            report = run_fascicoli_document_economic_presidio_for_current_context(
                limit=limit_per_tenant,
                actor=actor,
            )
        tenants.append({"tenant": "default", **report})
        for key in totals:
            totals[key] += int(report.get(key) or 0)

    errori = sum(1 for voce in tenants if _text(voce.get("error")))
    return {
        "ok": errori == 0 and bool(tenants),
        "job": "fascicoli_document_economic_presidio",
        "error": "" if tenants else "nessun contesto studio disponibile per il presidio",
        "source_of_truth": "sqlite/postgresql tenant-aware",
        "scan_mode": "incrementale_su_impronta_documentale",
        "tenants": tenants,
        "errors": errori,
        "totals": totals,
    }


__all__ = [
    "run_fascicoli_document_economic_presidio_for_all_tenants",
    "run_fascicoli_document_economic_presidio_for_current_context",
]
