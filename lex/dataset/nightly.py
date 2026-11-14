"""Esecuzione notturna governata per dataset Lex dello studio."""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .batch import (
    StudioDatasetBatchOptions,
    _document_from_ai_rows,
    build_studio_dataset_batch,
    load_document_ai_json_documents,
)
from .chunking import ChunkingOptions
from .models import StudioDatasetDocument
from .qa import QA_TEXT_POLICY_VERSION, QAGenerationPolicy


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


def _file_fingerprint(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError:
        return {"path": str(path), "exists": False, "size": 0, "mtime_ns": 0}
    return {
        "path": str(path),
        "exists": True,
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _dataset_options_fingerprint(
    *,
    max_documents: int | None,
    allow_sensitive_export: bool,
    include_pending_review_export: bool,
) -> dict[str, Any]:
    return {
        "qa_text_policy": QA_TEXT_POLICY_VERSION,
        "max_documents": int(max_documents or 0),
        "allow_sensitive_export": bool(allow_sensitive_export),
        "include_pending_review_export": bool(include_pending_review_export),
    }


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
    return _build_lex_dataset(
        tenant_id=tenant_id,
        source_fingerprint=_file_fingerprint(Path(document_ai_json_path)),
        load_documents=lambda: load_document_ai_json_documents(
            document_ai_json_path, tenant_id=tenant_id, max_documents=max_documents,
        ),
        output_root=output_root,
        max_documents=max_documents,
        allow_sensitive_export=allow_sensitive_export,
        include_pending_review_export=include_pending_review_export,
    )


def _build_lex_dataset(
    *,
    tenant_id: str,
    source_fingerprint: dict[str, Any],
    load_documents: Callable[[], list[StudioDatasetDocument]],
    output_root: str | Path,
    max_documents: int | None,
    allow_sensitive_export: bool,
    include_pending_review_export: bool,
    review_sql: bool = False,
) -> dict[str, Any]:
    root = Path(output_root)
    output_dir = root / _safe_slug(tenant_id, "tenant")
    started_at = _utc_now()
    options_fingerprint = _dataset_options_fingerprint(
        max_documents=max_documents,
        allow_sensitive_export=allow_sensitive_export,
        include_pending_review_export=include_pending_review_export,
    )
    latest_payload = _read_json(output_dir / "latest_job.json")
    latest_job = (
        latest_payload.get("latest_job")
        if isinstance(latest_payload, Mapping) and isinstance(latest_payload.get("latest_job"), Mapping)
        else {}
    )
    if (
        latest_job
        and latest_job.get("status") in {"completed", "skipped_unchanged"}
        and latest_job.get("source_fingerprint") == source_fingerprint
        and latest_job.get("dataset_options") == options_fingerprint
        and latest_job.get("output_files")
        and all(Path(path).is_file() for path in latest_job["output_files"])
    ):
        job = {
            "status": "skipped_unchanged",
            "tenant_id": tenant_id,
            "started_at": started_at,
            "completed_at": _utc_now(),
            "documents_count": int(latest_job.get("documents_count") or 0),
            "chunks_count": int(latest_job.get("chunks_count") or 0),
            "qa_pairs_count": int(latest_job.get("qa_pairs_count") or 0),
            "sensitive_documents_count": int(latest_job.get("sensitive_documents_count") or 0),
            "sensitive_chunks_count": int(latest_job.get("sensitive_chunks_count") or 0),
            "blocked_exports": list(latest_job.get("blocked_exports") or []),
            "output_files": list(latest_job.get("output_files") or []),
            "source_fingerprint": source_fingerprint,
            "dataset_options": options_fingerprint,
            "automatic_training": False,
            "external_training": False,
            "human_review_required": True,
            "scan_mode": "source_unchanged_skip",
            "message": "Dataset Lex invariato: Documenti AI non modificato, nessuna rilettura o rigenerazione.",
        }
        _append_job_history(root, job)
        _append_job_history(output_dir, job)
        return job
    try:
        documents = load_documents()
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
            review_sql=review_sql,
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
            "source_fingerprint": source_fingerprint,
            "dataset_options": options_fingerprint,
            "scan_mode": "source_changed_build",
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
            "source_fingerprint": source_fingerprint,
            "dataset_options": options_fingerprint,
            "scan_mode": "source_changed_build",
            "automatic_training": False,
            "external_training": False,
            "human_review_required": True,
            "message": f"Dataset Lex non preparato: {exc}",
        }
    _append_job_history(root, job)
    _append_job_history(output_dir, job)
    return job


def _config_value(config: Mapping[str, Any], key: str, default: Any = "") -> Any:
    return config.get(key) or os.getenv(key) or default


_TESTI_VERSIONE_CORRENTE = """
    WITH candidati AS (
        SELECT MAX(t.id) AS testo_id
        FROM fascicolo_documenti_ai_testi t
        CROSS JOIN fascicolo_documenti_ai d
        CROSS JOIN fascicoli f
        WHERE t.tenant_id=? AND d.id=t.document_id
            AND d.tenant_id=t.tenant_id AND d.fascicolo_id=t.fascicolo_id
            AND d.current_version_id=t.version_id AND f.id=t.fascicolo_id
        GROUP BY t.fascicolo_id, CASE WHEN length(d.sha256)>0 THEN d.sha256 ELSE d.id END
    )
"""
_RIGHE_DATASET = """
    FROM candidati c
    JOIN fascicolo_documenti_ai_testi t ON t.id=c.testo_id
    JOIN fascicolo_documenti_ai d ON d.id=t.document_id
        AND d.tenant_id=t.tenant_id AND d.fascicolo_id=t.fascicolo_id
"""


def _build_lex_dataset_from_sql(core, *, tenant_id: str, max_documents: int | None, **options: Any) -> dict[str, Any]:
    from pct.document_intelligence.read_view import source_snapshot

    with ExitStack() as stack:
        conn = stack.enter_context(source_snapshot(core)).conn
        metadata = conn.execute(
            _TESTI_VERSIONE_CORRENTE
            + "SELECT t.id, t.document_id, t.version_id, t.created_at, d.sha256, d.status, "
            "d.original_filename, d.mime_type " + _RIGHE_DATASET + " ORDER BY t.id",
            (tenant_id,),
        )
        impronta = hashlib.sha256()
        testo_ids = []
        for row in metadata:
            impronta.update(json.dumps(dict(row), default=str, sort_keys=True).encode("utf-8"))
            testo_ids.append(row["id"])
        if not testo_ids:
            return {"status": "skipped_empty", "tenant_id": tenant_id, "documents_count": 0,
                    "message": "Nessuna versione corrente con testo nell'archivio SQL dello studio."}

        def load_documents() -> list[StudioDatasetDocument]:
            documents = []
            # Riusa gli ID deduplicati della stessa fotografia. Un solo ordinamento
            # globale, su metadati: il testo integrale si legge per piccoli lotti.
            for start in range(0, len(testo_ids), 128):
                batch = testo_ids[start:start + 128]
                placeholders = ", ".join("?" for _ in batch)
                query = (
                    "SELECT t.document_id, t.fascicolo_id, t.version_id, t.extraction_engine, "
                    "t.text, t.pages_json, d.original_filename, d.safe_filename, "
                    "d.mime_type, d.sha256, d.status "
                    "FROM fascicolo_documenti_ai_testi t "
                    "JOIN fascicolo_documenti_ai d ON d.id=t.document_id "
                    "AND d.tenant_id=t.tenant_id AND d.fascicolo_id=t.fascicolo_id "
                    f"WHERE t.id IN ({placeholders}) AND length(trim(t.text))>0 ORDER BY t.id"
                )
                for row in conn.execute(query, batch):
                    payload = dict(row)
                    payload["pages"] = json.loads(payload.pop("pages_json") or "[]")
                    documents.append(_document_from_ai_rows(tenant_id, payload["fascicolo_id"], payload, payload))
                    if max_documents is not None and len(documents) >= max_documents:
                        break
                if max_documents is not None and len(documents) >= max_documents:
                    break
            stack.close()
            return documents

        return _build_lex_dataset(
            tenant_id=tenant_id,
            source_fingerprint={"backend": getattr(core, "backend_kind", "sqlite"), "sha256": impronta.hexdigest(),
                                "versioni": len(testo_ids), "review_store": "sqlite"},
            load_documents=load_documents,
            max_documents=max_documents,
            review_sql=True,
            **options,
        )


def _target_from_paths(slug: str, paths: Mapping[str, Any], database: Any = None) -> dict[str, Any]:
    fascicoli_db = Path(str(paths.get("FASCICOLI_DB") or ""))
    base = fascicoli_db.parent.parent if fascicoli_db.name else Path()
    studio_db = str(paths.get("STUDIO_DB") or "")
    if studio_db:
        base = Path(studio_db).parent
    return {
        "slug": slug,
        "database": database,
        "studio_db": studio_db,
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
            targets.append(_target_from_paths(slug, manager.percorsi_dati(slug, reconcile_aliases=False), studio.database))
    except Exception:
        targets = []

    if targets:
        return tuple(targets)

    fascicoli_db = str(config.get("FASCICOLI_DB") or "./fascicoli/fascicoli.json")
    return (_target_from_paths("studio", {**config, "FASCICOLI_DB": fascicoli_db}, config.get("TENANT_DATABASE_CONFIG")),)


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
    options_fingerprint = _dataset_options_fingerprint(
        max_documents=max_documents,
        allow_sensitive_export=allow_sensitive,
        include_pending_review_export=include_pending,
    )
    targets = _iter_targets(cfg)
    for target in targets:
        database = target.get("database")
        studio_db = str(target.get("studio_db") or "")
        mode = str(getattr(database, "normalized_mode", "") or "").upper()
        if studio_db and (mode in {"SQLITE", "POSTGRESQL"} or not mode and Path(studio_db).is_file()):
            from pct.core_storage_backend import build_core_storage_backend
            from pct.storage import StudioDB

            tenant_id = str(target["slug"])
            try:
                core = build_core_storage_backend(database, studio_db_path=studio_db, readonly=True)
                if core is None and mode == "POSTGRESQL":
                    raise RuntimeError("Archivio SQL PostgreSQL non disponibile.")
                if core is None:
                    core = StudioDB(studio_db, readonly=True, initialize_schema=False)
                try:
                    job = _build_lex_dataset_from_sql(
                        core, tenant_id=tenant_id, output_root=target["output_root"], max_documents=max_documents,
                        allow_sensitive_export=allow_sensitive, include_pending_review_export=include_pending,
                    )
                finally:
                    core.chiudi()
                if job["status"] == "skipped_empty":
                    skipped.append({"studio": tenant_id, "reason": job["message"]})
                else:
                    tenant_jobs.append(job)
            except Exception as exc:
                tenant_jobs.append({"status": "failed", "tenant_id": tenant_id, "message": str(exc)})
            continue
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
        output_root = Path(str(target.get("output_root") or ""))
        source_fingerprint = _file_fingerprint(document_ai_json)
        source_index_path = output_root / "source_index.json"
        source_index = _read_json(source_index_path)
        tenant_ids: tuple[str, ...] = ()
        if (
            isinstance(source_index, Mapping)
            and source_index.get("source_fingerprint") == source_fingerprint
            and source_index.get("dataset_options") == options_fingerprint
            and isinstance(source_index.get("tenant_ids"), list)
        ):
            tenant_ids = tuple(str(item or "").strip() for item in source_index.get("tenant_ids") or [] if str(item or "").strip())
        if not tenant_ids:
            tenant_ids = infer_document_ai_tenant_ids(document_ai_json)
            if tenant_ids:
                _write_json(
                    source_index_path,
                    {
                        "source_fingerprint": source_fingerprint,
                        "dataset_options": options_fingerprint,
                        "tenant_ids": list(tenant_ids),
                        "updated_at": _utc_now(),
                    },
                )
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
                    output_root=str(output_root),
                    max_documents=max_documents,
                    allow_sensitive_export=allow_sensitive,
                    include_pending_review_export=include_pending,
                )
            )

    completed = sum(1 for job in tenant_jobs if job.get("status") == "completed")
    skipped_unchanged = sum(1 for job in tenant_jobs if job.get("status") == "skipped_unchanged")
    failed = sum(1 for job in tenant_jobs if job.get("status") == "failed")
    documents = sum(int(job.get("documents_count") or 0) for job in tenant_jobs)
    chunks = sum(int(job.get("chunks_count") or 0) for job in tenant_jobs)
    qa_pairs = sum(int(job.get("qa_pairs_count") or 0) for job in tenant_jobs)
    return {
        "ok": failed == 0,
        "status": "failed" if failed else ("completed" if tenant_jobs else "parziale"),
        "completed_at": _utc_now(),
        "studios_checked": len(targets),
        "tenants_processed": len(tenant_jobs),
        "completed": completed,
        "skipped_unchanged": skipped_unchanged,
        "failed": failed,
        "studios_skipped": len(skipped),
        "skipped": skipped,
        "documents_count": documents,
        "chunks_count": chunks,
        "qa_pairs_count": qa_pairs,
        "automatic_training": False,
        "external_training": False,
        "human_review_required": True,
        "jobs": tenant_jobs,
        "summary": (
            f"Dataset Lex notturno: {completed} studi elaborati, {skipped_unchanged} invariati, "
            f"{documents} documenti, {chunks} blocchi, {qa_pairs} domande candidate. "
            "Nessun addestramento automatico avviato."
        ),
    }


__all__ = [
    "build_lex_dataset_for_document_ai_json",
    "infer_document_ai_tenant_ids",
    "run_lex_dataset_nightly",
]
