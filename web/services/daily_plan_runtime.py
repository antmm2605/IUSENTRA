"""Runtime tenant-aware del piano del giorno (Lex Oggi).

Costruisce repository, collettori e servizio a partire dai percorsi dati del
tenant (``g.data_paths`` in richiesta, ``percorsi_dati(slug)`` nello
scheduler). Il tenant NON arriva mai dal client: viene risolto lato server.

Il provider del presidio fascicoli riusa le funzioni già esistenti del
bridge React (testi documentali già estratti + riepilogo pagamenti veloce):
nessun OCR e nessuna estrazione vengono eseguiti in questo percorso.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from flask import current_app, g, has_app_context, has_request_context

from pct.daily_plan.clock import Clock, system_clock
from pct.daily_plan.collectors import Budget, CollectorContext
from pct.daily_plan.assignment import LawyerResolver, build_resolver_from_users
from pct.daily_plan.repository import DailyPlanRepository, derive_daily_plan_db_path
from pct.daily_plan.service import DailyPlanService

DEFAULT_BUDGET = Budget(max_items_per_source=500, max_fascicoli=60, max_seconds=60.0)


def _path_from_mapping(paths: Mapping[str, Any], key: str, default: str) -> str:
    value = paths.get(key)
    if value:
        return str(value)
    if has_app_context() and current_app.config.get(key):
        return str(current_app.config[key])
    return default


def current_tenant_label() -> str:
    """Slug tenant risolto lato server (mai dal client)."""
    if has_request_context():
        for name in ("tenant_context_slug", "tenant_slug"):
            value = str(getattr(g, name, "") or "").strip()
            if value:
                return value
        tenant = getattr(g, "tenant", None)
        value = str(getattr(tenant, "slug", "") or "").strip()
        if value:
            return value
    return "default"


def repository_from_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str = "default",
    clock: Clock | None = None,
) -> DailyPlanRepository:
    anchor = _path_from_mapping(
        paths, "GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"
    )
    db_path = str(paths.get("DAILY_PLAN_DB") or derive_daily_plan_db_path(anchor))
    postgres_dsn = ""
    try:
        from pct.postgres_runtime_support import resolve_runtime_postgres_dsn

        postgres_dsn = resolve_runtime_postgres_dsn(database=paths.get("database"))
    except Exception:
        postgres_dsn = ""
    return DailyPlanRepository(
        db_path,
        tenant_id=str(tenant_label or "default").strip().lower() or "default",
        postgres_dsn=postgres_dsn,
        clock=clock or system_clock(),
    )


def _agenda_store(paths: Mapping[str, Any]):
    from pct.agenda import Agenda

    return Agenda(db_path=_path_from_mapping(paths, "AGENDA_DB", "./agenda/appuntamenti.json"))


def _scadenziario_store(paths: Mapping[str, Any]):
    from pct.scadenziario import GestioneScadenziario

    return GestioneScadenziario(
        db_path=_path_from_mapping(paths, "SCADENZIARIO_DB", "./scadenziario/scadenze.json")
    )


def _fascicoli_store(paths: Mapping[str, Any]):
    from pct.fascicoli import GestioneFascicoli

    return GestioneFascicoli(
        db_path=_path_from_mapping(paths, "FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        documents_dir=_path_from_mapping(paths, "FASCICOLI_DOCS", "./fascicoli/documenti"),
        archive_dir=_path_from_mapping(paths, "FASCICOLI_ARCH", "./fascicoli/archivio"),
    )


def _preventivi_store(paths: Mapping[str, Any]):
    from pct.preventivi import GestionePreventivi

    return GestionePreventivi(
        db_path=_path_from_mapping(paths, "PREVENTIVI_DB", "./preventivi/preventivi.json"),
        sync_repository_on_init=False,
    )


def _fatturazione_store(paths: Mapping[str, Any]):
    from pct.fatturazione import GestioneFatturazione

    return GestioneFatturazione(
        db_path=_path_from_mapping(paths, "FATTURAZIONE_DB", "./fatturazione/parcelle.json")
    )


def _pec_repository(paths: Mapping[str, Any], tenant_label: str):
    from web.services.pec_pipeline_runtime import repository_from_paths as pec_repo

    return pec_repo(paths, tenant_label=tenant_label)


def _hot_fascicolo_ids(paths: Mapping[str, Any]) -> list[str]:
    """Fascicoli "caldi" dallo snapshot Quadro studio: priorità di analisi."""
    try:
        import json as _json

        snapshot_db = _path_from_mapping(
            paths,
            "WORKSPACE_INTELLIGENCE_DB",
            str(
                Path(
                    _path_from_mapping(
                        paths, "GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"
                    )
                ).with_name("workspace_intelligence.json")
            ),
        )
        payload = _json.loads(Path(snapshot_db).read_text(encoding="utf-8"))
        overview = payload.get("overview") or payload
        hot = overview.get("fascicoli_hot") or []
        return [str(item.get("id") or "") for item in hot if item.get("id")]
    except Exception:
        return []


def presidio_provider_factory(
    paths: Mapping[str, Any], *, clock: Clock
) -> Callable[[CollectorContext], Iterable[dict[str, Any]]]:
    """Provider delle azioni di presidio per fascicolo.

    Riusa i presidi puri con input GIÀ materializzati: testi documentali dal
    catalogo Document AI (nessun OCR) e riepilogo pagamenti veloce. Gli esiti
    dei depositi telematici arrivano dal presidio PEC, non da qui.
    """

    def provider(ctx: CollectorContext) -> Iterable[dict[str, Any]]:
        from pct.fascicolo_operational_presidio import build_fascicolo_operational_presidio
        from web.services.react_fascicoli_bridge import (
            _document_presidio_for_fascicolo,
            payment_summary_for_fascicolo_fast,
        )

        store = ctx.fascicoli_store
        if store is None:
            return
        try:
            fascicoli = list(store.tutti())
        except Exception:
            return

        hot_ids = _hot_fascicolo_ids(paths)
        order = {fid: idx for idx, fid in enumerate(hot_ids)}
        fascicoli.sort(key=lambda f: order.get(str(getattr(f, "id", "")), len(order)))

        processed = 0
        for fascicolo in fascicoli:
            fascicolo_id = str(getattr(fascicolo, "id", "") or "")
            if ctx.dirty_fascicoli is not None and fascicolo_id not in ctx.dirty_fascicoli:
                continue
            if processed >= ctx.budget.max_fascicoli:
                return
            processed += 1
            try:
                document_presidio = _document_presidio_for_fascicolo(fascicolo)
            except Exception:
                document_presidio = {"status": "non_disponibile", "actions": [], "warnings": []}
            try:
                payment_summary = payment_summary_for_fascicolo_fast(fascicolo)
            except Exception:
                payment_summary = {}
            try:
                presidio = build_fascicolo_operational_presidio(
                    fascicolo=fascicolo,
                    document_presidio=document_presidio,
                    notification_relata={},
                    payment_summary=payment_summary,
                    deposits=[],
                    duplicate_group=None,
                    sentenze_economiche=None,
                    today=clock.today(),
                )
            except Exception:
                continue
            yield {
                "fascicolo": {
                    "id": fascicolo_id,
                    "numero": str(getattr(fascicolo, "numero", "") or ""),
                    "titolo": str(getattr(fascicolo, "titolo", "") or ""),
                    "id_cliente": str(getattr(fascicolo, "id_cliente", "") or ""),
                    "avvocato_referente": str(getattr(fascicolo, "avvocato_referente", "") or ""),
                    "avvocato_dominus": str(getattr(fascicolo, "avvocato_dominus", "") or ""),
                },
                "actions": list(presidio.get("actions") or []),
            }

    return provider


def resolver_factory_from_paths(paths: Mapping[str, Any]) -> Callable[[], LawyerResolver]:
    def factory() -> LawyerResolver:
        try:
            from pct.auth import GestioneUtenti

            auth_db = _path_from_mapping(paths, "AUTH_DB", "./auth/utenti.json")
            if not Path(auth_db).exists():
                return LawyerResolver(users=[])
            audit_db = _path_from_mapping(paths, "AUDIT_DB", "./auth/audit.json")
            secret = (
                str(current_app.config.get("SECRET_KEY", "") or "daily-plan")
                if has_app_context()
                else "daily-plan"
            )
            gestore = GestioneUtenti(
                db_path=auth_db,
                audit_path=audit_db,
                secret_key=secret,
                crea_admin_se_vuoto=False,
            )
            return build_resolver_from_users(gestore.tutti(solo_attivi=True))
        except Exception:
            return LawyerResolver(users=[])

    return factory


def fascicoli_lookup_factory_from_paths(
    paths: Mapping[str, Any]
) -> Callable[[], dict[str, dict[str, Any]]]:
    def factory() -> dict[str, dict[str, Any]]:
        try:
            store = _fascicoli_store(paths)
            lookup: dict[str, dict[str, Any]] = {}
            for f in store.tutti(archiviati=True):
                fid = str(getattr(f, "id", "") or "")
                if not fid:
                    continue
                lookup[fid] = {
                    "numero": str(getattr(f, "numero", "") or ""),
                    "titolo": str(getattr(f, "titolo", "") or ""),
                    "nome_cliente": str(getattr(f, "nome_cliente", "") or ""),
                    "id_cliente": str(getattr(f, "id_cliente", "") or ""),
                    "avvocato_referente": str(getattr(f, "avvocato_referente", "") or ""),
                    "avvocato_dominus": str(getattr(f, "avvocato_dominus", "") or ""),
                }
            return lookup
        except Exception:
            return {}

    return factory


def context_factory_from_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    clock: Clock,
    budget: Budget = DEFAULT_BUDGET,
) -> Callable[[set[str] | None], CollectorContext]:
    def factory(dirty: set[str] | None) -> CollectorContext:
        def _safe(builder, *args):
            try:
                return builder(*args)
            except Exception:
                return None

        return CollectorContext(
            tenant_id=str(tenant_label or "default").strip().lower() or "default",
            clock=clock,
            budget=budget,
            agenda_store=_safe(_agenda_store, paths),
            scadenziario_store=_safe(_scadenziario_store, paths),
            fascicoli_store=_safe(_fascicoli_store, paths),
            pec_repository=_safe(_pec_repository, paths, tenant_label),
            preventivi_store=_safe(_preventivi_store, paths),
            fatturazione_store=_safe(_fatturazione_store, paths),
            presidio_provider=presidio_provider_factory(paths, clock=clock),
            dirty_fascicoli=dirty,
        )

    return factory


def service_from_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    clock: Clock | None = None,
    budget: Budget = DEFAULT_BUDGET,
) -> DailyPlanService:
    clock = clock or system_clock()
    repository = repository_from_paths(paths, tenant_label=tenant_label, clock=clock)
    return DailyPlanService(
        repository,
        context_factory=context_factory_from_paths(
            paths, tenant_label=tenant_label, clock=clock, budget=budget
        ),
        resolver_factory=resolver_factory_from_paths(paths),
        fascicoli_lookup_factory=fascicoli_lookup_factory_from_paths(paths),
        clock=clock,
    )


def _current_paths() -> Mapping[str, Any]:
    if has_request_context():
        paths = getattr(g, "data_paths", None)
        if paths:
            return paths
    if has_app_context():
        return current_app.config
    return {}


def service_for_current_request() -> DailyPlanService:
    return service_from_paths(_current_paths(), tenant_label=current_tenant_label())


def repository_for_current_request() -> DailyPlanRepository:
    return repository_from_paths(_current_paths(), tenant_label=current_tenant_label())


def run_daily_plan_for_all_tenants(
    app,
    *,
    mode: str = "incremental",
    actor: str = "IUSENTRA scheduler",
) -> dict[str, Any]:
    """Esegue il piano del giorno per tutti gli studi attivi.

    ``mode="full"``: riconciliazione completa (giornaliera, 07:30 Europe/Rome).
    ``mode="incremental"``: smaltisce dirty entities e job accodati; se un
    tenant non ha nulla da rielaborare viene saltato (no-op economico).
    Nessuna scrittura applicativa automatica: il piano è una proiezione.
    """
    from web.services.fascicoli_presidi_runtime import _active_tenants, _attach_tenant_context

    tenants: list[dict[str, Any]] = []
    totals = {"tenants": 0, "skipped": 0, "errors": 0, "items_written": 0}

    def _run_for_current(tenant_label: str) -> dict[str, Any] | None:
        service = service_from_paths(_current_paths(), tenant_label=tenant_label)
        repo = service.repository
        job = repo.claim_next_job("full_rebuild")
        effective_mode = mode
        if job is not None:
            effective_mode = "full"
        elif mode != "full":
            job = repo.claim_next_job("incremental_refresh")
            if job is None and repo.pending_dirty_count() == 0:
                return None  # niente da fare: no-op economico
        try:
            if effective_mode == "full":
                report = service.rebuild_full(actor=actor)
            else:
                report = service.refresh_incremental(actor=actor)
            if job is not None:
                repo.finish_job(job["id"], status="done", report=report)
            return report
        except Exception as exc:
            if job is not None:
                repo.finish_job(job["id"], status="failed", report={"error": str(exc)[:200]})
            raise

    active = _active_tenants(app)
    if active:
        from pct.tenant import GestioneTenant

        manager = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
        for studio in active:
            slug = str(getattr(studio, "slug", "") or "").strip().lower()
            try:
                with app.test_request_context(f"/__scheduler/daily-plan/{slug}"):
                    _attach_tenant_context(manager, studio)
                    report = _run_for_current(slug)
            except Exception as exc:
                totals["errors"] += 1
                tenants.append({"tenant": slug, "ok": False, "error": str(exc)[:180]})
                continue
            if report is None:
                totals["skipped"] += 1
                tenants.append({"tenant": slug, "skipped": True})
            else:
                totals["tenants"] += 1
                totals["items_written"] += int(report.get("items_written") or 0)
                tenants.append({"tenant": slug, **{k: report[k] for k in (
                    "mode", "items_written", "users_planned", "signals_upserted",
                ) if k in report}})
    else:
        try:
            with app.test_request_context("/__scheduler/daily-plan/default"):
                g.multi_tenant_enabled = False
                g.tenant_context_missing = False
                g.tenant_context_slug = ""
                report = _run_for_current("default")
        except Exception as exc:
            totals["errors"] += 1
            tenants.append({"tenant": "default", "ok": False, "error": str(exc)[:180]})
            report = None
        if report is None and not totals["errors"]:
            totals["skipped"] += 1
            tenants.append({"tenant": "default", "skipped": True})
        elif report is not None:
            totals["tenants"] += 1
            totals["items_written"] += int(report.get("items_written") or 0)
            tenants.append({"tenant": "default", "mode": report.get("mode"),
                            "items_written": report.get("items_written")})

    return {
        "ok": totals["errors"] == 0,
        "job": "studio_daily_operational_plan" if mode == "full" else "daily_plan_incremental_refresh",
        "mode": mode,
        "tenants": tenants,
        "totals": totals,
    }


def mark_dirty_for_paths(
    paths: Mapping[str, Any],
    *,
    tenant_label: str,
    entity_type: str,
    entity_ids: Iterable[str],
    reason: str = "",
) -> int:
    """Hook best-effort: registra entità cambiate per il refresh incrementale."""
    try:
        repo = repository_from_paths(paths, tenant_label=tenant_label)
        return repo.mark_dirty(entity_type, entity_ids, reason=reason)
    except Exception:
        return 0
