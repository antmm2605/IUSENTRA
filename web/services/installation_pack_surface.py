"""Superficie admin per Product Pack, Studio Local Pack e Update Pack."""

from __future__ import annotations

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


def _service_runtime_cards(product_pack: dict[str, Any], observability: dict[str, Any]) -> list[dict[str, Any]]:
    local_ai_runtime = dict((((observability.get("providers") or {}).get("local_ai") or {}).get("runtime")) or {})
    ai_ready = str(local_ai_runtime.get("status") or "").strip().lower() in {"ready", "available"}
    auto_index = bool(current_app.config.get("LOCAL_AI_AUTO_INDEX_DOCUMENTS"))
    updater_ready = bool(product_pack.get("signature"))

    items: list[dict[str, Any]] = []
    for entry in product_pack.get("services") or []:
        service_id = str(entry.get("service_id") or "")
        status = "ok"
        detail = str(entry.get("responsibility") or "")
        if service_id == "iusentra-lex" and not ai_ready:
            status = "warning"
            detail = "Runtime Lex presente nel Product Pack ma AI locale non ancora pronta nel runtime corrente."
        elif service_id == "iusentra-embed" and not auto_index:
            status = "warning"
            detail = "Servizio embeddings installato, ma indicizzazione automatica documenti non attiva nelle impostazioni correnti."
        elif service_id == "iusentra-updater" and not updater_ready:
            status = "warning"
            detail = "Updater presente, ma il manifest update corrente non risulta ancora firmato."
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
