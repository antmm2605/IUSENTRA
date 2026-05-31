from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pct.installation_secrets import ensure_installation_local_key
from pct.tenant import GestioneTenant, StudioLegale


SYSTEM_SERVICE_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "service_id": "iusentra-web",
        "label": "Cabina web locale",
        "scope": "product",
        "responsibility": "Interfaccia web locale o LAN studio.",
    },
    {
        "service_id": "iusentra-lex",
        "label": "Orchestratore Lex",
        "scope": "product",
        "responsibility": "Routing AI, guardrail, retrieval e policy di risposta.",
    },
    {
        "service_id": "iusentra-embed",
        "label": "Indicizzazione embeddings",
        "scope": "product",
        "responsibility": "Embedding, chunking e reindex locale.",
    },
    {
        "service_id": "iusentra-jobs",
        "label": "Job scheduler locale",
        "scope": "product",
        "responsibility": "OCR, ingestione, housekeeping, backup e autotest.",
    },
    {
        "service_id": "iusentra-telematico",
        "label": "Connettore telematico",
        "scope": "product",
        "responsibility": "PST, PAT, PTT, PDP e adapter di acquisizione.",
    },
    {
        "service_id": "iusentra-updater",
        "label": "Updater governato",
        "scope": "product",
        "responsibility": "Aggiornamenti firmati, migrazioni e refresh knowledge pubblica.",
    },
)

PRODUCT_PUBLIC_SEED_FILES: tuple[tuple[str, str, str], ...] = (
    ("config/ai-policy.json", "policy/ai-policy.json", "policy"),
    (
        "pct/sql/20260417_legal_taxonomy_operational_tables.sql",
        "taxonomy/legal_taxonomy_operational_tables.sql",
        "taxonomy",
    ),
)

STUDIO_LOCAL_PACK_DIRECTORIES: tuple[str, ...] = (
    "studio_data",
    "studio_data/db",
    "studio_data/vectors",
    "studio_data/memory",
    "studio_data/memory/facts",
    "studio_data/memory/timeline",
    "studio_data/memory/profiles",
    "studio_data/memory/economic",
    "studio_data/documents",
    "studio_data/attachments",
    "studio_data/cache",
    "studio_data/jobs",
    "studio_data/backups",
    "studio_data/audit",
    "studio_data/protected_material",
)


@dataclass(slots=True)
class PackBootstrapResult:
    installation: dict[str, Any]
    product_pack: dict[str, Any]
    update_pack: dict[str, Any]
    studio_local_packs: list[dict[str, Any]]
    system_root: str


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_relpath(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve())).replace("\\", "/")
    except Exception:
        return str(path.resolve()).replace("\\", "/")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


_SENSITIVE_JSON_KEY_PARTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "access_key",
    "private_key",
    "master_key",
    "signing_key",
    "pin",
)


def _redact_json_sensitive_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_JSON_KEY_PARTS):
                redacted[str(key)] = "[redatto]" if item not in (None, "", []) else item
            else:
                redacted[str(key)] = _redact_json_sensitive_values(item)
        return redacted
    if isinstance(value, list):
        return [_redact_json_sensitive_values(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_json_sensitive_values(item) for item in value]
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        _redact_json_sensitive_values(payload),
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    )
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == encoded:
                return
        except Exception:
            pass
    path.write_text(encoded, encoding="utf-8")  # codeql[py/clear-text-storage-sensitive-data]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _manifest_hash_payload(payload: dict[str, Any]) -> str:
    canonical_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"manifest_hash_sha256", "signature"}
    }
    canonical = json.dumps(
        canonical_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    ).encode("utf-8")
    return _sha256_bytes(canonical)


def _attach_manifest_hash(payload: dict[str, Any]) -> dict[str, Any]:
    payload.pop("signature", None)
    payload["integrity_method"] = "sha256-canonical-json"
    payload["manifest_hash_sha256"] = _manifest_hash_payload(payload)
    return payload


def resolve_system_pack_root(registry_path: str) -> Path:
    registry = Path(registry_path).resolve()
    return registry.parent / "system"


def derive_installation_pack_repository_db_path(registry_path: str) -> str:
    root = resolve_system_pack_root(registry_path)
    return str(root / "installation" / "installation_pack.db")


def _system_paths(system_root: Path) -> dict[str, Path]:
    return {
        "root": system_root,
        "product_root": system_root / "product",
        "product_runtime": system_root / "product" / "runtime",
        "product_models": system_root / "product" / "models",
        "product_public": system_root / "product" / "public_knowledge",
        "product_manifests": system_root / "product" / "manifests",
        "updates_root": system_root / "updates",
        "updates_inbox": system_root / "updates" / "inbox",
        "updates_history": system_root / "updates" / "history",
        "installation_root": system_root / "installation",
        "installation_config": system_root / "installation" / "config",
        "installation_keys": system_root / "installation" / "keys",
        "installation_logs": system_root / "installation" / "logs",
    }


def _iter_public_seed_specs(app_root: Path) -> list[dict[str, Any]]:
    seeds: list[dict[str, Any]] = []
    for source_rel, target_rel, kind in PRODUCT_PUBLIC_SEED_FILES:
        source = app_root / source_rel
        if source.exists() and source.is_file():
            seeds.append(
                {
                    "source": source,
                    "target_rel": Path(target_rel),
                    "kind": kind,
                }
            )
    taxonomy_root = app_root / "pct" / "sql" / "tassonomia"
    if taxonomy_root.exists():
        for source in sorted(path for path in taxonomy_root.rglob("*") if path.is_file()):
            seeds.append(
                {
                    "source": source,
                    "target_rel": Path("taxonomy") / "tassonomia" / source.relative_to(taxonomy_root),
                    "kind": "taxonomy",
                }
            )
    return seeds


def _copy_public_knowledge(app_root: Path, public_root: Path) -> list[dict[str, Any]]:
    public_root.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for spec in _iter_public_seed_specs(app_root):
        source = Path(spec["source"])
        target = public_root / Path(spec["target_rel"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or _sha256_file(target) != _sha256_file(source):
            shutil.copy2(source, target)
        entries.append(
            {
                "id": str(Path(spec["target_rel"]).with_suffix("")).replace("\\", "/"),
                "kind": str(spec["kind"]),
                "source_path": str(source),
                "pack_path": str(target),
                "sha256": _sha256_file(target),
                "size_bytes": target.stat().st_size,
                "relative_pack_path": str(Path(spec["target_rel"])).replace("\\", "/"),
            }
        )
    return entries


def _previous_version_from_changelog(app_root: Path, current_version: str) -> str:
    changelog = app_root / "CHANGELOG.md"
    if not changelog.exists():
        return current_version
    matches = re.findall(r"^##\s+([0-9]+\.[0-9]+\.[0-9]+)\s+-\s+", changelog.read_text(encoding="utf-8"), flags=re.MULTILINE)
    cleaned = [item.strip() for item in matches if item.strip()]
    if len(cleaned) < 2:
        return current_version
    return cleaned[1] if cleaned[0] == current_version else cleaned[0]


def ensure_installation_identity(
    *,
    app_root: str | Path,
    registry_path: str,
    app_version: str,
    requested_by: str = "SUPERADMIN",
) -> dict[str, Any]:
    app_root_path = Path(app_root).resolve()
    system_root = resolve_system_pack_root(registry_path)
    paths = _system_paths(system_root)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)

    identity_path = paths["installation_config"] / "installation_identity.json"
    master_key_path = paths["installation_keys"] / "master.key"
    previous_identity = _read_json(identity_path)
    installation_id = previous_identity.get("installation_id")
    if not isinstance(installation_id, str) or not installation_id.strip():
        installation_id = uuid4().hex
    created_at = previous_identity.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        created_at = _utcnow_iso()
    previous_requested_by = previous_identity.get("requested_by")
    if not isinstance(previous_requested_by, str) or not previous_requested_by.strip():
        previous_requested_by = requested_by

    identity = {
        "installation_id": installation_id,
        "created_at": created_at,
        "requested_by": previous_requested_by,
        "app_root": str(app_root_path),
        "app_version": app_version,
        "product_root": str(paths["product_root"]),
        "studio_local_scope": "I dati degli studi restano tenant-aware sotto data/tenants e non vengono distribuiti nel Product Pack.",
        "superadmin_scope": "Il SUPERADMIN installa, aggiorna e governa Product Pack, Update Pack e bootstrap macchina.",
    }

    ensure_installation_local_key(master_key_path)

    protected_material_labels = ("database", "documents", "backups", "session-material")
    secure_material_items: list[dict[str, Any]] = []
    for label in protected_material_labels:
        secure_material_items.append(
            {
                "purpose": label,
                "storage": "protected local file",
            }
        )
    identity.update(
        {
            "app_version": app_version,
            "updated_at": _utcnow_iso(),
            "system_root": str(system_root),
            "encryption_profile": "per-installation protected material",
            "secure_material_store": "installation local protected files",
            "secure_material_items": secure_material_items,
            "system_directories": {
                key: str(value)
                for key, value in paths.items()
                if key not in {"root", "installation_keys"}
            },
        }
    )
    _write_json(identity_path, identity)
    return identity


def build_product_pack_manifest(
    *,
    app_root: str | Path,
    registry_path: str,
    app_version: str,
    installation_identity: dict[str, Any],
) -> dict[str, Any]:
    app_root_path = Path(app_root).resolve()
    system_paths = _system_paths(resolve_system_pack_root(registry_path))
    public_knowledge_entries = _copy_public_knowledge(app_root_path, system_paths["product_public"])

    payload = {
        "pack_type": "ProductPack",
        "version": app_version,
        "generated_at": _utcnow_iso(),
        "installation_id": installation_identity["installation_id"],
        "app_build": app_version,
        "lex_build": app_version,
        "pack_root": str(system_paths["product_root"]),
        "runtime_root": str(system_paths["product_runtime"]),
        "models_root": str(system_paths["product_models"]),
        "public_knowledge_root": str(system_paths["product_public"]),
        "public_knowledge_manifest": public_knowledge_entries,
        "services": list(SYSTEM_SERVICE_DEFINITIONS),
        "knowledge_boundary": {
            "public_knowledge": "Norme pubbliche, policy, tassonomie e template riusabili tra installazioni.",
            "forbidden_payloads": [
                "atti reali di clienti",
                "vector db di altri studi",
                "memory privata di studi terzi",
                "cache operative di altri tenant",
            ],
        },
        "installer": {
            "managed_by": "SUPERADMIN",
            "bootstrap_scope": "Macchina locale / server locale dello studio",
            "installation_identity_path": str(system_paths["installation_config"] / "installation_identity.json"),
        },
        "updater": {
            "history_root": str(system_paths["updates_history"]),
            "inbox_root": str(system_paths["updates_inbox"]),
            "integrity_method": "sha256-canonical-json",
        },
    }
    _attach_manifest_hash(payload)
    _write_json(system_paths["product_manifests"] / "product_pack.json", payload)
    return payload


def ensure_studio_local_pack(
    *,
    tenant_manager: GestioneTenant,
    studio: StudioLegale,
    installation_identity: dict[str, Any],
) -> dict[str, Any]:
    tenant_manager._inizializza_directory(studio.slug)  # noqa: SLF001 - bootstrap governato del tenant
    tenant_root = tenant_manager._data_dir(studio.slug)
    for relative in STUDIO_LOCAL_PACK_DIRECTORIES:
        (tenant_root / relative).mkdir(parents=True, exist_ok=True)

    paths = tenant_manager.percorsi_dati(studio.slug, reconcile_aliases=False)
    private_memory = {
        "facts_path": str(tenant_root / "studio_data" / "memory" / "facts"),
        "timeline_path": str(tenant_root / "studio_data" / "memory" / "timeline"),
        "profiles_path": str(tenant_root / "studio_data" / "memory" / "profiles"),
        "economic_path": str(tenant_root / "studio_data" / "memory" / "economic"),
    }
    documents_root = str(Path(paths["FASCICOLI_DOCS"]).resolve())
    attachments_root = str(Path(paths["PORTALE_UPLOADS"]).resolve())
    cache_root = str(tenant_root / "studio_data" / "cache")
    vectors_root = str(tenant_root / "studio_data" / "vectors")
    jobs_root = str(tenant_root / "studio_data" / "jobs")
    backup_root = str(tenant_root / "backup")
    audit_root = str(tenant_root / "auth")
    protected_material_root = str(tenant_root / "studio_data" / "protected_material")
    compatibility_paths = {
        "core_db": paths["STUDIO_DB"],
        "clienti_json": paths["CLIENTI_DB"],
        "fascicoli_json": paths["FASCICOLI_DB"],
        "document_store": paths["FASCICOLI_DOCS"],
        "attachments_store": paths["PORTALE_UPLOADS"],
        "vector_store_operativo": paths["LOCAL_AI_DB"],
        "workspace_intelligence": paths["WORKSPACE_INTELLIGENCE_DB"],
        "redaction_memory": paths["REDACTION_ASSISTANT_DB"],
        "audit_log": paths["AUDIT_DB"],
        "backup_root": paths["BACKUP_DIR"],
        "config_studio": paths["CONFIG_STUDIO_DB"],
    }

    payload = {
        "pack_type": "StudioLocalPack",
        "generated_at": _utcnow_iso(),
        "installation_id": installation_identity["installation_id"],
        "studio_id": studio.id,
        "studio_slug": studio.slug,
        "studio_nome": studio.nome,
        "managed_by": "SUPERADMIN",
        "tenant_root": str(tenant_root),
        "database_backend": studio.database.effective_runtime_kind,
        "database_mode": studio.database.normalized_mode,
        "encryption_profile": installation_identity.get(
            "encryption_profile",
            "per-installation protected material",
        ),
        "paths": {
            "pack_root": str(tenant_root / "studio_data"),
            "db_root": str(tenant_root / "studio_data" / "db"),
            "vectors_root": vectors_root,
            "documents_root": documents_root,
            "attachments_root": attachments_root,
            "cache_root": cache_root,
            "jobs_root": jobs_root,
            "backup_root": backup_root,
            "audit_root": audit_root,
            "protected_material_root": protected_material_root,
        },
        "private_memory": private_memory,
        "compatibility_paths": compatibility_paths,
        "knowledge_boundary": {
            "private_memory": "Fascicoli, clienti, facts, timeline, profili e stato economico restano locali a questo studio.",
            "product_boundary": "Il Product Pack non deve includere vector store, cache o documenti di questo tenant.",
        },
        "secure_material_references": installation_identity.get("secure_material_items", []),
    }
    _attach_manifest_hash(payload)
    _write_json(tenant_root / "config" / "studio_local_pack.json", payload)
    return payload


def build_update_pack_manifest(
    *,
    app_root: str | Path,
    registry_path: str,
    app_version: str,
    installation_identity: dict[str, Any],
    product_pack: dict[str, Any],
) -> dict[str, Any]:
    app_root_path = Path(app_root).resolve()
    system_paths = _system_paths(resolve_system_pack_root(registry_path))
    previous_version = _previous_version_from_changelog(app_root_path, app_version)

    migrations: list[dict[str, Any]] = []
    sql_root = app_root_path / "pct" / "sql"
    for path in sorted(sql_root.rglob("*.sql")):
        migrations.append(
            {
                "name": path.name,
                "relative_path": _safe_relpath(path, app_root_path),
                "sha256": _sha256_file(path),
            }
        )

    payload = {
        "pack_type": "UpdatePack",
        "generated_at": _utcnow_iso(),
        "installation_id": installation_identity["installation_id"],
        "from_version": previous_version,
        "to_version": app_version,
        "history_root": str(system_paths["updates_history"]),
        "inbox_root": str(system_paths["updates_inbox"]),
        "integrity_method": "sha256-canonical-json",
        "migrations": migrations,
        "service_updates": [
            {
                "service_id": item["service_id"],
                "label": item["label"],
                "target_version": app_version,
            }
            for item in SYSTEM_SERVICE_DEFINITIONS
        ],
        "public_knowledge_updates": [
            {
                "id": item["id"],
                "kind": item["kind"],
                "sha256": item["sha256"],
            }
            for item in (product_pack.get("public_knowledge_manifest") or [])
        ],
        "governance": {
            "maintenance_mode": "locale",
            "backup_required": True,
            "rollback_required": True,
            "superadmin_only": True,
        },
    }
    _attach_manifest_hash(payload)
    _write_json(system_paths["updates_history"] / f"update_pack_{app_version}.json", payload)
    _write_json(system_paths["updates_root"] / "current_update_pack.json", payload)
    return payload


def bootstrap_pack_governance(
    *,
    app_root: str | Path,
    registry_path: str,
    app_version: str,
    tenant_manager: GestioneTenant | None = None,
) -> PackBootstrapResult:
    tm = tenant_manager or GestioneTenant(registry_path=registry_path)
    installation = ensure_installation_identity(
        app_root=app_root,
        registry_path=registry_path,
        app_version=app_version,
    )
    product_pack = build_product_pack_manifest(
        app_root=app_root,
        registry_path=registry_path,
        app_version=app_version,
        installation_identity=installation,
    )
    studio_local_packs = [
        ensure_studio_local_pack(
            tenant_manager=tm,
            studio=studio,
            installation_identity=installation,
        )
        for studio in tm.lista()
    ]
    update_pack = build_update_pack_manifest(
        app_root=app_root,
        registry_path=registry_path,
        app_version=app_version,
        installation_identity=installation,
        product_pack=product_pack,
    )
    return PackBootstrapResult(
        installation=installation,
        product_pack=product_pack,
        update_pack=update_pack,
        studio_local_packs=studio_local_packs,
        system_root=str(resolve_system_pack_root(registry_path)),
    )
