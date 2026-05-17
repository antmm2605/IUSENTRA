"""Esecuzione notturna governata per dataset Lex dello studio."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .batch import (
    StudioDatasetBatchOptions,
    build_studio_dataset_batch,
    load_document_ai_json_documents,
)
from .chunking import ChunkingOptions
from .qa import QAGenerationPolicy


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si", "attivo"}


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_slug(value: Any, fallback: str = "studio") -> str:
    raw = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(value or "").strip().lower())
    cleaned = "-".join(part for part in raw.split("-") if part)
    return cleaned or fallback


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _append_job_history(root: Path, job: dict[str, Any]) -> None:
    latest_path = root / "latest_job.json"
    history_path = root / "jobs.json"
    existing = _read_json(history_path)
    jobs = list(existing.get("jobs") or []) if isinstance(existing, Mapping) else []
    jobs.insert(0, dict(job))
    _write_json(latest_path, {"latest_job": job})
    _write_json(history_path, {"jobs": jobs[:50], "latest_job": job})


def infer_document_ai_tenant_ids(document_ai_json_path: str | Path) -> tuple[str, ...]:
    """Legge i tenant realmente presenti nel fallback JSON Documenti AI."""
    payload = _read_json(Path(document_ai_json_path))
    if not isinstance(payload, Mapping):
        return ()
    tenants: list[str] = []
    for section in ("documents", "texts"):
        rows = payload.get(section)
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            tenant = str(row.get("tenant_id") or "").strip()
            if tenant and tenant not in tenants:
                tenants.append(tenant)
    return tuple(tenants)


def build_lex_dataset_for_document_ai_json(
    *,
    tenant_id: str,
    document_ai_json_path: str | Path,
    output_root: str | Path,
    max_documents: int | None = None,
    allow_sensitive_export: bool = False,
    include_pending_review_export: bool = False,
) -> dict[str, Any]:
    """Prepara artefatti locali per revisione Lex senza avviare training."""
    root = Path(output_root)
    output_dir = root / _safe_slug(tenant_id, "tenant")
    started_at = _utc_now()
    try:
        documents = load_document_ai_json_documents(
            document_ai_json_path,
            tenant_id=tenant_id,
            max_documents=max_documents,
        )
        result = build_studio_dataset_batch(
            documents,
            StudioDatasetBatchOptions(
                tenant_id=tenant_id,
                max_documents=max_documents,
                dry_run=False,
                allow_sensitive_export=allow_sensitive_export,
                include_pending_review_export=include_pending_review_export,
                chunking_options=ChunkingOptions(),
                qa_policy=QAGenerationPolicy(min_chunk_chars=80),
            ),
            output_dir=output_dir,
        )
        summary = result.summary()
        job = {
            "status": "completed",
            "tenant_id": tenant_id,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "documents_count": summary["documents_count"],
            "chunks_count": summary["chunks_count"],
            "qa_pairs_count": summary["qa_pairs_count"],
            "sensitive_documents_count": summary["sensitive_documents_count"],
            "sensitive_chunks_count": summary["sensitive_chunks_count"],
            "blocked_exports": summary["blocked_exports"],
            "output_files": summary["output_files"],
            "automatic_training": False,
            "external_training": False,
            "human_review_required": True,
            "message": "Dataset Lex preparato per revisione: nessun addestramento automatico avviato.",
        }
    except Exception as exc:
        job = {
            "status": "failed",
            "tenant_id": tenant_id,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "documents_count": 0,
            "chunks_count": 0,
            "qa_pairs_count": 0,
            "blocked_exports": [],
            "output_files": [],
            "automatic_training": False,
            "external_training": False,
            "human_review_required": True,
            "message": f"Dataset Lex non preparato: {exc}",
        }
    _append_job_history(root, job)
    return job


def _config_value(config: Mapping[str, Any], key: str, default: Any = "") -> Any:
    return config.get(key) or os.getenv(key) or default


def _target_from_paths(slug: str, paths: Mapping[str, Any]) -> dict[str, Any]:
    fascicoli_db = Path(str(paths.get("FASCICOLI_DB") or ""))
    base = fascicoli_db.parent.parent if fascicoli_db.name else Path()
    return {
        "slug": slug,
        "data_root": str(base),
        "document_ai_json": str(base / "fascicoli" / "documenti_ai" / "documenti_ai.json"),
        "output_root": str(base / "intelligence" / "lex_dataset"),
    }


def _fallback_document_ai_json(config: Mapping[str, Any]) -> Path:
    fascicoli_db = Path(str(config.get("FASCICOLI_DB") or "./fascicoli/fascicoli.json"))
    base = fascicoli_db.parent.parent if fascicoli_db.name else Path("data")
    return base / "fascicoli" / "documenti_ai" / "documenti_ai.json"


def _iter_targets(config: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    targets: list[dict[str, Any]] = []
    try:
        from pct.tenant import GestioneTenant, StatoTenant

        registry = str(config.get("TENANTS_REGISTRY") or "./data/tenants.json")
        manager = GestioneTenant(registry_path=registry)
        for studio in manager.lista():
            if getattr(studio, "stato", "") == StatoTenant.SOSPESO:
                continue
            slug = str(getattr(studio, "slug", "") or "").strip().lower()
            if not slug:
                continue
            targets.append(_target_from_paths(slug, manager.percorsi_dati(slug)))
    except Exception:
        targets = []

    if targets:
        return tuple(targets)

    fascicoli_db = str(config.get("FASCICOLI_DB") or "./fascicoli/fascicoli.json")
    return (_target_from_paths("studio", {"FASCICOLI_DB": fascicoli_db}),)


def run_lex_dataset_nightly(*, app: Any | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Esegue il job notturno dataset Lex per tutti gli studi disponibili."""
    cfg: Mapping[str, Any] = config or getattr(app, "config", {}) or {}
    max_documents_raw = _config_value(cfg, "IUSENTRA_LEX_DATASET_MAX_DOCUMENTS", "")
    max_documents = _positive_int(max_documents_raw, 0) or None
    local_sensitive_storage = _config_value(cfg, "IUSENTRA_LEX_DATASET_LOCAL_SENSITIVE_STORAGE", "")
    allow_sensitive = _truthy(
        local_sensitive_storage
        if str(local_sensitive_storage).strip()
        else _config_value(cfg, "IUSENTRA_LEX_DATASET_ALLOW_SENSITIVE_EXPORT", "1")
    )
    include_pending = _truthy(_config_value(cfg, "IUSENTRA_LEX_DATASET_EXPORT_PENDING_REVIEW", "0"))

    tenant_jobs: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    shared_document_ai_json = _fallback_document_ai_json(cfg)
    for target in _iter_targets(cfg):
        document_ai_json = Path(str(target.get("document_ai_json") or ""))
        used_shared_document_ai = False
        if not document_ai_json.exists():
            if shared_document_ai_json.exists():
                document_ai_json = shared_document_ai_json
                used_shared_document_ai = True
            else:
                skipped.append({
                    "studio": str(target.get("slug") or "studio"),
                    "reason": "Archivio Documenti AI non presente.",
                })
                continue
        tenant_ids = infer_document_ai_tenant_ids(document_ai_json)
        if not tenant_ids:
            skipped.append({
                "studio": str(target.get("slug") or "studio"),
                "reason": "Nessun documento indicizzato da Documenti AI.",
            })
            continue
        if used_shared_document_ai:
            slug = str(target.get("slug") or "").strip().lower()
            tenant_ids = tuple(tenant_id for tenant_id in tenant_ids if tenant_id.lower() == slug)
            if not tenant_ids:
                skipped.append({
                    "studio": str(target.get("slug") or "studio"),
                    "reason": "Archivio Documenti AI condiviso senza documenti dello studio.",
                })
                continue
        for tenant_id in tenant_ids:
            tenant_jobs.append(
                build_lex_dataset_for_document_ai_json(
                    tenant_id=tenant_id,
                    document_ai_json_path=document_ai_json,
                    output_root=str(target.get("output_root") or ""),
                    max_documents=max_documents,
                    allow_sensitive_export=allow_sensitive,
                    include_pending_review_export=include_pending,
                )
            )

    completed = sum(1 for job in tenant_jobs if job.get("status") == "completed")
    failed = sum(1 for job in tenant_jobs if job.get("status") == "failed")
    documents = sum(int(job.get("documents_count") or 0) for job in tenant_jobs)
    chunks = sum(int(job.get("chunks_count") or 0) for job in tenant_jobs)
    qa_pairs = sum(int(job.get("qa_pairs_count") or 0) for job in tenant_jobs)
    return {
        "ok": failed == 0,
        "status": "completed" if failed == 0 else "failed",
        "completed_at": _utc_now(),
        "studios_checked": len(_iter_targets(cfg)),
        "tenants_processed": len(tenant_jobs),
        "completed": completed,
        "failed": failed,
        "skipped": skipped,
        "documents_count": documents,
        "chunks_count": chunks,
        "qa_pairs_count": qa_pairs,
        "automatic_training": False,
        "external_training": False,
        "human_review_required": True,
        "jobs": tenant_jobs,
        "summary": (
            f"Dataset Lex notturno: {completed} studi elaborati, "
            f"{documents} documenti, {chunks} blocchi, {qa_pairs} domande candidate. "
            "Nessun addestramento automatico avviato."
        ),
    }


__all__ = [
    "build_lex_dataset_for_document_ai_json",
    "infer_document_ai_tenant_ids",
    "run_lex_dataset_nightly",
]
