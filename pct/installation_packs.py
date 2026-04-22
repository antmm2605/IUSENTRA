from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct.tenant import GestioneTenant, StudioLegale


SYSTEM_SERVICE_DEFINITIONS: tuple[dict[str, str], ...] = (
    {
        "service_id": "hacs-web",
        "label": "Cabina web locale",
        "scope": "product",
        "responsibility": "Interfaccia web locale o LAN studio.",
    },
    {
        "service_id": "hacs-lex",
        "label": "Orchestratore Lex",
        "scope": "product",
        "responsibility": "Routing AI, guardrail, retrieval e policy di risposta.",
    },
    {
        "service_id": "hacs-embed",
        "label": "Indicizzazione embeddings",
        "scope": "product",
        "responsibility": "Embedding, chunking e reindex locale.",
    },
    {
        "service_id": "hacs-jobs",
        "label": "Job scheduler locale",
        "scope": "product",
        "responsibility": "OCR, ingestione, housekeeping, backup e autotest.",
    },
    {
        "service_id": "hacs-telematico",
        "label": "Connettore telematico",
        "scope": "product",
        "responsibility": "PST, PAT, PTT, PDP e adapter di acquisizione.",
    },
    {
        "service_id": "hacs-updater",
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
    "studio_data/keys",
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


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == encoded:
                return
        except Exception:
            pass
    path.write_text(encoded, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _ensure_private_file(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(raw)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _load_secret(path: Path) -> bytes:
    if not path.exists():
        return b""
    raw = path.read_bytes().strip()
    if not raw:
        return b""
    try:
        return base64.urlsafe_b64decode(raw)
    except Exception:
        return raw


def _store_secret(path: Path, raw: bytes) -> None:
    _ensure_private_file(path, base64.urlsafe_b64encode(raw))


def _derive_secret(master: bytes, purpose: str) -> bytes:
    return hmac.new(master, purpose.encode("utf-8"), hashlib.sha256).digest()


def _sign_payload(payload: dict[str, Any], signing_key: bytes) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default).encode("utf-8")
    return hmac.new(signing_key, canonical, hashlib.sha256).hexdigest()


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
    signing_key_path = paths["installation_keys"] / "product_signing.key"
    database_key_path = paths["installation_keys"] / "database.key"
    documents_key_path = paths["installation_keys"] / "documents.key"
    backups_key_path = paths["installation_keys"] / "backups.key"
    tokens_key_path = paths["installation_keys"] / "tokens.key"

    identity = _read_json(identity_path)
    if not identity:
        identity = {
            "installation_id": str(secrets.token_hex(16)),
            "created_at": _utcnow_iso(),
            "requested_by": requested_by,
            "app_root": str(app_root_path),
            "app_version": app_version,
            "product_root": str(paths["product_root"]),
            "studio_local_scope": "I dati degli studi restano tenant-aware sotto data/tenants e non vengono distribuiti nel Product Pack.",
            "superadmin_scope": "Il SUPERADMIN installa, aggiorna e governa Product Pack, Update Pack e bootstrap macchina.",
        }

    master = _load_secret(master_key_path)
    if not master:
        master = secrets.token_bytes(32)
        _store_secret(master_key_path, master)

    signing_key = _load_secret(signing_key_path)
    if not signing_key:
        signing_key = _derive_secret(master, "product-signing")
        _store_secret(signing_key_path, signing_key)

    derived_specs = {
        "database": database_key_path,
        "documents": documents_key_path,
        "backups": backups_key_path,
        "tokens": tokens_key_path,
    }
    derived_payload: list[dict[str, Any]] = []
    for label, path in derived_specs.items():
        secret = _load_secret(path)
        if not secret:
            secret = _derive_secret(master, f"installation:{label}")
            _store_secret(path, secret)
        derived_payload.append(
            {
                "purpose": label,
                "path": str(path),
                "fingerprint": _sha256_bytes(secret),
            }
        )

    identity.update(
        {
            "app_version": app_version,
            "updated_at": _utcnow_iso(),
            "system_root": str(system_root),
            "encryption_profile": "master-key-per-installation",
            "master_key_path": str(master_key_path),
            "master_key_fingerprint": _sha256_bytes(master),
            "signing_key_path": str(signing_key_path),
            "signing_key_fingerprint": _sha256_bytes(signing_key),
            "derived_keys": derived_payload,
            "system_directories": {
                key: str(value)
                for key, value in paths.items()
                if key not in {"root"}
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
    signing_key = _load_secret(Path(installation_identity["signing_key_path"]))

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
            "signature_method": "hmac-sha256",
        },
    }
    payload["signature"] = _sign_payload(payload, signing_key)
    _write_json(system_paths["product_manifests"] / "product_pack.json", payload)
    return payload


def ensure_studio_local_pack(
    *,
    tenant_manager: GestioneTenant,
    studio: StudioLegale,
    installation_identity: dict[str, Any],
) -> dict[str, Any]:
    tenant_manager._inizializza_directory(studio.slug)  # noqa: SLF001 - bootstrap governato del tenant
    tenant_root = tenant_manager.data_dir(studio.slug)
    for relative in STUDIO_LOCAL_PACK_DIRECTORIES:
        (tenant_root / relative).mkdir(parents=True, exist_ok=True)

    paths = tenant_manager.percorsi_dati(studio.slug)
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
    local_keys_root = str(tenant_root / "studio_data" / "keys")
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

    signing_key = _load_secret(Path(installation_identity["signing_key_path"]))
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
        "encryption_profile": installation_identity.get("encryption_profile", "master-key-per-installation"),
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
            "keys_root": local_keys_root,
        },
        "private_memory": private_memory,
        "compatibility_paths": compatibility_paths,
        "knowledge_boundary": {
            "private_memory": "Fascicoli, clienti, facts, timeline, profili e stato economico restano locali a questo studio.",
            "product_boundary": "Il Product Pack non deve includere vector store, cache o documenti di questo tenant.",
        },
        "derived_key_fingerprints": installation_identity.get("derived_keys", []),
    }
    payload["signature"] = _sign_payload(payload, signing_key)
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
    signing_key = _load_secret(Path(installation_identity["signing_key_path"]))
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
        "signature_method": "hmac-sha256",
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
    payload["signature"] = _sign_payload(payload, signing_key)
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
