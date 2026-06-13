"""Superficie admin per Product Pack, Studio Local Pack e Update Pack."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from flask import current_app

from pct import __version__ as APP_VERSION
from pct.installation_pack_repository import InstallationPackRepository
from pct.installation_packs import bootstrap_pack_governance
from pct.postgres_runtime_support import resolve_runtime_postgres_dsn
from pct.tenant import GestioneTenant
from web.services.observability_runtime import build_observability_payload


def _tenant_manager() -> GestioneTenant:
    registry = current_app.config.get("TENANTS_REGISTRY", "./data/tenants.json")
    return GestioneTenant(registry_path=registry)


def _repository(registry_path: str) -> InstallationPackRepository:
    postgres_dsn = resolve_runtime_postgres_dsn(
        config=current_app.config,
        env_url_keys=(
            "PCT_INSTALLATION_PACK_POSTGRES_URL",
            "PCT_INSTALLATION_PACK_POSTGRES_DSN",
        ),
    )
    return InstallationPackRepository.from_registry_path(
        registry_path,
        postgres_dsn=postgres_dsn,
    )


def _lex_product_runtime_status() -> tuple[bool, str]:
    required_modules = (
        "lex.orchestrator_workflow",
        "lex.gateway.router",
        "lex.providers.local_ai_service",
    )
    errors: list[str] = []
    for module_name in required_modules:
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            current_app.logger.warning("Runtime Lex non importabile per %s: %s", module_name, exc)
            errors.append(f"{module_name}: modulo non disponibile")
    if errors:
        return False, "; ".join(errors)
    return True, "Runtime Lex installato: orchestrazione, gateway provider e bridge AI locale sono importabili."


def _service_runtime_cards(product_pack: dict[str, Any], observability: dict[str, Any]) -> list[dict[str, Any]]:
    auto_index = bool(current_app.config.get("LOCAL_AI_AUTO_INDEX_DOCUMENTS"))
    updater_ready = bool(product_pack.get("manifest_hash_sha256") or product_pack.get("signature"))
    lex_ready, lex_detail = _lex_product_runtime_status()

    items: list[dict[str, Any]] = []
    for entry in product_pack.get("services") or []:
        service_id = str(entry.get("service_id") or "")
        status = "ok"
        detail = str(entry.get("responsibility") or "")
        if service_id == "iusentra-lex":
            status = "ok" if lex_ready else "danger"
            detail = lex_detail if lex_ready else f"Runtime Lex non importabile nel prodotto corrente: {lex_detail}"
        elif service_id == "iusentra-embed" and not auto_index:
            status = "warning"
            detail = "Servizio embeddings installato, ma indicizzazione automatica documenti non attiva nelle impostazioni correnti."
        elif service_id == "iusentra-updater" and not updater_ready:
            status = "warning"
            detail = "Updater presente, ma il manifest corrente non espone ancora un riferimento di integrita'."
        items.append(
            {
                "service_id": service_id,
                "label": str(entry.get("label") or service_id),
                "status": status,
                "scope": str(entry.get("scope") or ""),
                "detail": detail,
            }
        )
    return items


def _runtime_dependency_cards(observability: dict[str, Any]) -> list[dict[str, Any]]:
    local_ai = dict(((observability.get("providers") or {}).get("local_ai") or {}))
    settings = dict(local_ai.get("settings") or {})
    runtime = dict(local_ai.get("runtime") or {})
    counts = dict(local_ai.get("counts") or {})
    enabled = bool(settings.get("enabled", True))
    runtime_status = str(runtime.get("status") or "").strip()
    runtime_online = bool(local_ai.get("runtime_online")) or runtime_status.lower() in {"ready", "available"}
    has_reserved_runtime_detail = bool(str(runtime.get("last_error") or "").strip())
    api_base_url = str(runtime.get("api_base_url") or "").strip()
    chunks_pending = int(counts.get("chunks_pending") or 0)
    chunks_total = int(counts.get("chunks_total") or 0)

    if not enabled:
        status = "warning"
        detail = "AI locale disabilitata nelle impostazioni correnti: Lex resta installato ma non puo' usare il provider locale."
    elif runtime_online:
        status = "ok"
        detail = "AI locale pronta: il provider locale risulta operativo per Lex e per gli embeddings."
    else:
        status = "warning"
        reason = f"stato {runtime_status}" if runtime_status else "stato non disponibile"
        if has_reserved_runtime_detail:
            reason = f"{reason}; dettaglio tecnico disponibile nei log operativi riservati"
        detail = f"AI locale abilitata ma non pronta sul PC dello studio: {reason}."

    meta: list[str] = []
    if api_base_url:
        meta.append(f"Indirizzo configurato: {api_base_url}")
    if chunks_total or chunks_pending:
        meta.append(f"Chunk RAG: {chunks_pending} pendenti su {chunks_total}")

    return [
        {
            "dependency_id": "local_ai_provider",
            "label": "Provider AI locale",
            "status": status,
            "detail": detail,
            "meta": meta,
        }
    ]


def _select_studio_pack(studio_packs: list[dict[str, Any]], selected_slug: str = "") -> dict[str, Any] | None:
    wanted = str(selected_slug or "").strip().lower()
    if wanted:
        for payload in studio_packs:
            if str(payload.get("studio_slug") or "").strip().lower() == wanted:
                return payload
    return studio_packs[0] if studio_packs else None


def build_installation_pack_surface(*, selected_slug: str = "") -> dict[str, Any]:
    registry_path = str(current_app.config.get("TENANTS_REGISTRY", "./data/tenants.json"))
    app_root = Path(__file__).resolve().parents[2]
    tm = _tenant_manager()
    bootstrap = bootstrap_pack_governance(
        app_root=app_root,
        registry_path=registry_path,
        app_version=APP_VERSION,
        tenant_manager=tm,
    )
    repo = _repository(registry_path)
    repo.upsert_product_pack(bootstrap.product_pack)
    repo.upsert_update_pack(bootstrap.update_pack)
    for payload in bootstrap.studio_local_packs:
        repo.upsert_studio_local_pack(payload)

    observability = build_observability_payload(current_app._get_current_object())
    selected_studio_pack = _select_studio_pack(bootstrap.studio_local_packs, selected_slug)

    return {
        "headline": {
            "product_services": len(bootstrap.product_pack.get("services") or []),
            "public_knowledge_assets": len(bootstrap.product_pack.get("public_knowledge_manifest") or []),
            "studio_local_packs": len(bootstrap.studio_local_packs),
            "update_migrations": len(bootstrap.update_pack.get("migrations") or []),
        },
        "installation": bootstrap.installation,
        "product_pack": bootstrap.product_pack,
        "update_pack": bootstrap.update_pack,
        "repository": repo.storage_stats(),
        "service_runtime": _service_runtime_cards(bootstrap.product_pack, observability),
        "runtime_dependencies": _runtime_dependency_cards(observability),
        "studios": [
            {
                "slug": str(payload.get("studio_slug") or ""),
                "nome": str(payload.get("studio_nome") or ""),
                "database_backend": str(payload.get("database_backend") or ""),
                "selected": bool(selected_studio_pack and payload.get("studio_slug") == selected_studio_pack.get("studio_slug")),
            }
            for payload in bootstrap.studio_local_packs
        ],
        "selected_studio_pack": selected_studio_pack,
        "superadmin_rule": "Il SUPERADMIN installa il prodotto, governa i pack e aggiorna la macchina. Gli studi usano solo il loro Studio Local Pack tenant-aware.",
    }
