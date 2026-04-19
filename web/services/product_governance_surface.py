"""Superficie admin per governance prodotto: storage, policy, migrazione e audit."""

from __future__ import annotations

from typing import Any

from flask import current_app

from pct.tenant import DB_MODE_INFO, GestioneTenant
from pct.golden_paths import build_golden_path_payload
from pct.product_governance import (
    STORAGE_PARITY_REGISTRY,
    build_authorization_model_payload,
    build_e2e_flow_payload,
    build_migration_program_payload,
    build_observability_capabilities_payload,
    build_storage_parity_payload,
)
from web.services.admin_surfaces_shared import get_auth_manager
from web.services.observability_runtime import build_observability_payload


def _tenant_manager() -> GestioneTenant:
    registry = current_app.config.get("TENANTS_REGISTRY", "./data/tenants.json")
    return GestioneTenant(registry_path=registry)


def _resolve_selected_studio(selected_slug: str = "") -> tuple[GestioneTenant, list[Any], Any | None]:
    tm = _tenant_manager()
    studios = tm.lista()
    wanted = str(selected_slug or "").strip().lower()
    studio = tm.get(wanted) if wanted else None
    if studio is None and studios:
        studio = studios[0]
    return tm, studios, studio


def _mode_label(mode: str) -> str:
    normalized = str(mode or "").strip().upper()
    return str(DB_MODE_INFO.get(normalized, {}).get("nome") or normalized or "n.d.")


def _effective_backend_label(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized == "postgresql":
        return "PostgreSQL tenant-aware"
    if normalized == "sqlite":
        return "SQL locale tenant-aware"
    if normalized == "json":
        return "JSON locale tenant-aware"
    return "n.d."


def _build_backend_policy(*, studio: Any | None) -> dict[str, Any]:
    structured_domains = [entry for entry in STORAGE_PARITY_REGISTRY if entry.module_id != "local_ai"]
    explicit_exceptions = [
        {
            "label": "Documenti e allegati",
            "detail": "Documenti fascicolo, archivio e allegati restano su filesystem tenant-aware anche quando i metadati stanno su SQLite o PostgreSQL.",
        },
        {
            "label": "Buste e upload telematici",
            "detail": "File di deposito, buste, upload PST/PDP/PAT e artefatti telematici restano filesystem-first per tenant.",
        },
        {
            "label": "AI locale e modelli",
            "detail": "Runtime AI locale, modelli, cache embedding e artefatti host-first restano su filesystem e SQLite tecnico locale.",
        },
        {
            "label": "JSON come ponte controllato",
            "detail": "JSON resta solo per bootstrap, export, import storico o recovery controllato; non deve tornare backend invisibile quando il tenant usa SQLite o PostgreSQL.",
        },
    ]
    if studio is None:
        return {
            "selected_studio": None,
            "studios": [],
            "selected_mode": "",
            "selected_mode_label": "n.d.",
            "effective_backend_kind": "",
            "effective_backend_label": "n.d.",
            "alignment_status": "secondary",
            "alignment_label": "Nessuno studio selezionato",
            "alignment_detail": "La matrice sotto resta una capability di piattaforma finche' non scegli uno studio tenant-aware.",
            "structured_domains_total": len(structured_domains),
            "aligned_domains": 0,
            "explicit_exceptions": explicit_exceptions,
            "policy_title": "Nessun backend strutturato selezionato",
            "policy_detail": "Seleziona uno studio per vedere quale backend governa davvero tutti i dati strutturati tenant-aware.",
        }

    selected_mode = str(studio.database.normalized_mode or "").strip().upper()
    effective_kind = str(studio.database.effective_runtime_kind or "").strip().lower()
    effective_label = _effective_backend_label(effective_kind)
    aligned_domains = 0
    if effective_kind == "postgresql":
        aligned_domains = sum(1 for entry in structured_domains if entry.postgres_read and entry.postgres_write)
    elif effective_kind == "sqlite":
        aligned_domains = len(structured_domains)
    elif effective_kind == "json":
        aligned_domains = sum(1 for entry in structured_domains if entry.json_read and entry.json_write)

    if effective_kind == "postgresql":
        alignment_status = "success"
        alignment_label = "Backend strutturato unico attivo"
        alignment_detail = (
            "Questo studio usa PostgreSQL come backend effettivo per tutti i dati strutturati tenant-aware. "
            "Restano fuori dal database solo le eccezioni architetturali esplicite indicate sotto."
        )
    elif effective_kind == "sqlite":
        alignment_status = "success"
        alignment_label = "Backend strutturato unico attivo"
        alignment_detail = (
            "Questo studio usa SQL locale tenant-aware come backend effettivo per tutti i dati strutturati tenant-aware. "
            "Restano fuori dal database solo le eccezioni architetturali esplicite indicate sotto."
        )
    elif selected_mode == "POSTGRESQL":
        alignment_status = "warning"
        alignment_label = "Cutover PostgreSQL non ancora attivo"
        alignment_detail = (
            "Lo studio e' configurato per PostgreSQL, ma il backend effettivo non e' ancora passato in cutover. "
            "Finche' la connessione e il cutover core non risultano attivi, il tenant non puo' essere considerato davvero su PostgreSQL."
        )
    else:
        alignment_status = "secondary"
        alignment_label = "Backend JSON ancora in uso"
        alignment_detail = (
            "Lo studio sta ancora usando JSON come backend effettivo dei dati strutturati. "
            "SQLite o PostgreSQL diventano reali solo dopo la migrazione tenant-aware e il relativo cutover."
        )

    policy_title = (
        f"Tutti i dati strutturati tenant-aware di questo studio lavorano su {effective_label}."
        if effective_kind in {"sqlite", "postgresql"}
        else "Il backend strutturato unico dello studio non e' ancora stato chiuso sul database atteso."
    )
    policy_detail = (
        "La matrice sotto descrive la capability tecnica della piattaforma. "
        f"Per lo studio selezionato conta invece il backend effettivo: {effective_label}."
    )

    return {
        "selected_studio": {
            "slug": studio.slug,
            "nome": studio.nome,
        },
        "selected_mode": selected_mode,
        "selected_mode_label": _mode_label(selected_mode),
        "effective_backend_kind": effective_kind,
        "effective_backend_label": effective_label,
        "core_runtime_enabled": bool(studio.database.core_runtime_enabled),
        "connection_ok": bool(studio.database.connessione_ok),
        "alignment_status": alignment_status,
        "alignment_label": alignment_label,
        "alignment_detail": alignment_detail,
        "structured_domains_total": len(structured_domains),
        "aligned_domains": max(aligned_domains, 0),
        "explicit_exceptions": explicit_exceptions,
        "policy_title": policy_title,
        "policy_detail": policy_detail,
    }


def build_product_governance_surface(*, selected_slug: str = "") -> dict[str, Any]:
    auth_manager = get_auth_manager()
    auth_stats = auth_manager.statistiche()
    recent_audit = [evento.to_dict() for evento in auth_manager.audit_log(limit=8)]
    observability = build_observability_payload(current_app._get_current_object())
    _, studios, studio = _resolve_selected_studio(selected_slug)
    storage = build_storage_parity_payload()
    authorization = build_authorization_model_payload()
    migration = build_migration_program_payload()
    e2e = build_e2e_flow_payload()
    golden_paths = build_golden_path_payload()
    observability_product = build_observability_capabilities_payload(
        audit_events=int(auth_stats.get("totale_eventi_audit", 0) or 0),
        runtime_ok=bool(observability.get("ok")),
    )
    backend_policy = _build_backend_policy(studio=studio)

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
            "storage_default_label": _effective_backend_label(str((observability.get("storage") or {}).get("default_mode") or "")),
            "scheduler_worker_mode": bool(observability.get("scheduler_worker_mode")),
            "ocr_enabled": bool((observability.get("ocr") or {}).get("enabled")),
            "local_ai_status": str((((observability.get("providers") or {}).get("local_ai") or {}).get("runtime") or {}).get("status") or "n.d."),
        },
        "studios": [
            {
                "slug": studio_item.slug,
                "nome": studio_item.nome,
                "selected": bool(studio and studio_item.slug == studio.slug),
                "selected_mode": studio_item.database.normalized_mode,
                "effective_runtime_kind": studio_item.database.effective_runtime_kind,
            }
            for studio_item in studios
        ],
        "backend_policy": backend_policy,
        "storage": storage,
        "authorization": authorization,
        "migration": migration,
        "e2e": e2e,
        "golden_paths": golden_paths,
        "observability": observability_product,
        "recent_audit": recent_audit,
    }
