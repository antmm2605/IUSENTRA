"""Rigenera il testo Document AI mancante per i documenti dei fascicoli."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.document_intelligence.sources import collect_fascicolo_document_sources
from pct.fascicolo_document_catalog import document_ai_texts_for_catalog
from pct.tenant import GestioneTenant
from web.services.pec_pipeline_runtime import repository_from_paths


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _source_issue(source: Any) -> str:
    if not bool(getattr(source, "supported", False)):
        return "formato_non_supportato"
    content = getattr(source, "content_bytes", None)
    if content is not None:
        return "" if len(content) > 0 else "file_vuoto"
    path = getattr(source, "content_path", None)
    if path is None:
        return "percorso_fisico_mancante"
    try:
        if not path.is_file():
            return "file_fisico_non_disponibile"
        if path.stat().st_size <= 0:
            return "file_vuoto"
    except OSError as exc:
        return f"file_fisico_non_accessibile:{type(exc).__name__}"
    return ""


def _document_ids(documents: list[Any]) -> set[str]:
    return {
        _text(getattr(document, "id", ""))
        for document in documents
        if _text(getattr(document, "id", ""))
    }


def _source_key(fascicolo_id: str, source: Any) -> str:
    return "|".join(
        (
            _text(fascicolo_id),
            _text(getattr(source, "source_id", "")),
            _text(getattr(source, "sha256", "")),
        )
    )


def _texts_for_fascicolo(
    *,
    tenant_id: str,
    fascicolo_id: str,
    documents: list[Any],
    fascicoli_db_path: str,
    documents_root: str,
    structured_db: Any,
) -> dict[str, str]:
    storage_root = Path(documents_root).resolve().parent / "documenti_ai"
    return document_ai_texts_for_catalog(
        tenant_ids=[tenant_id, "default", "single-studio"],
        fascicolo_id=fascicolo_id,
        documents=documents,
        fascicoli_db_path=fascicoli_db_path,
        structured_db=structured_db,
        storage_root=storage_root,
        allow_extracted_files_fallback=False,
    )


def _select_missing_sources(
    *,
    repo: Any,
    paths: dict[str, Any],
    limit: int,
    include_archived: bool,
    exclude_source_keys: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    fascicoli_manager = repo._fascicoli_manager()
    fascicoli = fascicoli_manager.tutti(archiviati=include_archived)
    fascicoli_db_path = _text(paths.get("FASCICOLI_DB"))
    documents_root = _text(paths.get("FASCICOLI_DOCS"))
    structured_db = getattr(fascicoli_manager, "_studio_db", None)
    stats = {
        "fascicoli_seen": 0,
        "documents_seen": 0,
        "documents_with_text": 0,
        "documents_missing_text": 0,
        "processable_missing_text": 0,
        "source_unavailable": 0,
        "skipped_attempted_this_run": 0,
        "selected": 0,
    }
    excluded = set(exclude_source_keys or set())
    groups: list[dict[str, Any]] = []
    selected = 0
    for fascicolo in fascicoli:
        fascicolo_id = _text(getattr(fascicolo, "id", ""))
        if not fascicolo_id:
            continue
        documents = list(getattr(fascicolo, "documenti", []) or [])
        if not documents:
            continue
        stats["fascicoli_seen"] += 1
        stats["documents_seen"] += len(documents)
        texts = _texts_for_fascicolo(
            tenant_id=repo.tenant_id,
            fascicolo_id=fascicolo_id,
            documents=documents,
            fascicoli_db_path=fascicoli_db_path,
            documents_root=documents_root,
            structured_db=structured_db,
        )
        known_document_ids = _document_ids(documents)
        stats["documents_with_text"] += len(set(texts) & known_document_ids)
        missing_ids = known_document_ids - set(texts)
        stats["documents_missing_text"] += len(missing_ids)
        if not missing_ids:
            continue
        sources = collect_fascicolo_document_sources(
            tenant_id=repo.tenant_id,
            fascicolo_id=fascicolo_id,
            fascicolo=fascicolo,
            documents_root=documents_root,
        )
        pending_sources = []
        for source in sources:
            source_id = _text(getattr(source, "source_id", ""))
            if source_id not in missing_ids:
                continue
            issue = _source_issue(source)
            if issue:
                stats["source_unavailable"] += 1
                continue
            stats["processable_missing_text"] += 1
            if _source_key(fascicolo_id, source) in excluded:
                stats["skipped_attempted_this_run"] += 1
                continue
            if selected >= limit:
                continue
            pending_sources.append(source)
            selected += 1
        if pending_sources:
            groups.append({"fascicolo": fascicolo, "fascicolo_id": fascicolo_id, "sources": pending_sources})
        if selected >= limit:
            break
    stats["selected"] = selected
    return groups, stats


def _result_payload(
    *,
    tenants: list[dict[str, Any]],
    completed: bool,
    applied: bool,
) -> dict[str, Any]:
    totals = {
        "tenants": len(tenants),
        "cycles": sum(int(item.get("totals", {}).get("cycles", 0)) for item in tenants),
        "selected": sum(int(item.get("totals", {}).get("selected", 0)) for item in tenants),
        "indexed_documents": sum(int(item.get("totals", {}).get("indexed_documents", 0)) for item in tenants),
        "repaired_documents": sum(int(item.get("totals", {}).get("repaired_documents", 0)) for item in tenants),
        "unrepaired_attempted_documents": sum(
            int(item.get("totals", {}).get("unrepaired_attempted_documents", 0)) for item in tenants
        ),
        "errors": sum(int(item.get("totals", {}).get("errors", 0)) for item in tenants),
        "processable_missing_text": sum(
            int((item.get("last_scan") or {}).get("processable_missing_text", 0)) for item in tenants
        ),
    }
    return {
        "ok": bool(completed and applied and totals["errors"] == 0 and totals["processable_missing_text"] == 0),
        "completed": completed,
        "applied": applied,
        "source_of_truth": "sqlite/postgresql tenant-aware",
        "scan_mode": "explicit_missing_text_backfill",
        "totals": totals,
        "tenants": tenants,
    }


def run_tenant_cycles(
    *,
    registry: Path,
    tenant: str,
    limit: int,
    max_cycles: int,
    until_idle: bool,
    pause_seconds: float,
    include_archived: bool = False,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if studio.slug.casefold() == tenant.casefold()]
    if not studios:
        return {"ok": False, "tenant": tenant, "errors": [f"Studio non trovato: {tenant}"]}
    paths = manager.percorsi_dati(tenant, reconcile_aliases=False, ensure_baseline=False)
    repo = repository_from_paths(paths, tenant_label=tenant)
    fascicoli_manager = repo._fascicoli_manager()
    service = repo._document_ai_service_for_fascicoli(fascicoli_manager)
    user_context = {"user_id": "document-text-backfill", "skip_permission_check": True}
    cycles: list[dict[str, Any]] = []
    totals = {
        "cycles": 0,
        "selected": 0,
        "indexed_documents": 0,
        "indexing_skipped": 0,
        "repaired_documents": 0,
        "unrepaired_attempted_documents": 0,
        "errors": 0,
    }
    last_scan: dict[str, int] = {}
    idle = False
    attempted_source_keys: set[str] = set()
    for cycle in range(1, max(1, max_cycles) + 1):
        started = time.monotonic()
        groups, scan = _select_missing_sources(
            repo=repo,
            paths=dict(paths),
            limit=max(1, limit),
            include_archived=include_archived,
            exclude_source_keys=attempted_source_keys,
        )
        last_scan = dict(scan)
        selected_count = int(scan.get("selected") or 0)
        if selected_count <= 0:
            idle = int(scan.get("processable_missing_text") or 0) == 0
            item = {
                "cycle": cycle,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                **scan,
                "indexed_documents": 0,
                "indexing_skipped": 0,
                "repaired_documents": 0,
                "errors": [],
                "samples": [],
            }
            cycles.append(item)
            totals["cycles"] += 1
            if int(scan.get("skipped_attempted_this_run") or 0):
                totals["unrepaired_attempted_documents"] = int(scan.get("skipped_attempted_this_run") or 0)
            break
        cycle_errors: list[str] = []
        samples: list[dict[str, str]] = []
        indexed = 0
        skipped = 0
        repaired = 0
        for group in groups:
            fascicolo = group["fascicolo"]
            fascicolo_id = _text(group["fascicolo_id"])
            sources = list(group["sources"])
            for source in sources:
                attempted_source_keys.add(_source_key(fascicolo_id, source))
            if checkpoint_path is not None:
                partial = {
                    "tenant": tenant,
                    "cycle": cycle,
                    "phase": "document_text_indexing",
                    "fascicolo_id": fascicolo_id,
                    "documents": [
                        {
                            "document_id": _text(getattr(source, "source_id", "")),
                            "filename": _text(getattr(source, "filename", "")),
                            "sha256": _text(getattr(source, "sha256", "")),
                        }
                        for source in sources[:20]
                    ],
                }
                _write_json_atomic(
                    checkpoint_path,
                    _result_payload(
                        tenants=[
                            {
                                "tenant": tenant,
                                "completed": False,
                                "idle": False,
                                "totals": totals,
                                "last_scan": last_scan,
                                "cycles": cycles,
                                "current": partial,
                            }
                        ],
                        completed=False,
                        applied=True,
                    ),
                )
            before = _texts_for_fascicolo(
                tenant_id=repo.tenant_id,
                fascicolo_id=fascicolo_id,
                documents=list(getattr(fascicolo, "documenti", []) or []),
                fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
                documents_root=_text(paths.get("FASCICOLI_DOCS")),
                structured_db=getattr(fascicoli_manager, "_studio_db", None),
            )
            result = service.process_lex_indexing_sources(
                repo.tenant_id,
                fascicolo_id,
                sources,
                user_context,
                retry_errors=True,
            )
            indexed += int(getattr(result, "indexed", 0) or 0)
            skipped += int(getattr(result, "skipped", 0) or 0)
            for error in list(getattr(result, "errors", []) or [])[:20]:
                cycle_errors.append(f"{fascicolo_id}: {error}")
            after = _texts_for_fascicolo(
                tenant_id=repo.tenant_id,
                fascicolo_id=fascicolo_id,
                documents=list(getattr(fascicolo, "documenti", []) or []),
                fascicoli_db_path=_text(paths.get("FASCICOLI_DB")),
                documents_root=_text(paths.get("FASCICOLI_DOCS")),
                structured_db=getattr(fascicoli_manager, "_studio_db", None),
            )
            source_ids = {_text(getattr(source, "source_id", "")) for source in sources}
            repaired_ids = sorted(source_ids & (set(after) - set(before)))
            repaired += len(repaired_ids)
            for source in sources:
                if len(samples) >= 30:
                    break
                samples.append(
                    {
                        "fascicolo_id": fascicolo_id,
                        "document_id": _text(getattr(source, "source_id", "")),
                        "filename": _text(getattr(source, "filename", "")),
                    }
                )
        item = {
            "cycle": cycle,
            "elapsed_seconds": round(time.monotonic() - started, 3),
            **scan,
            "indexed_documents": indexed,
            "indexing_skipped": skipped,
            "repaired_documents": repaired,
            "errors": cycle_errors[:30],
            "samples": samples,
        }
        cycles.append(item)
        totals["cycles"] += 1
        totals["selected"] += selected_count
        totals["indexed_documents"] += indexed
        totals["indexing_skipped"] += skipped
        totals["repaired_documents"] += repaired
        totals["errors"] += len(cycle_errors)
        totals["unrepaired_attempted_documents"] = max(
            0,
            len(attempted_source_keys) - totals["repaired_documents"],
        )
        idle = False
        if checkpoint_path is not None:
            _write_json_atomic(
                checkpoint_path,
                {
                    "ok": False,
                    "completed": False,
                    "applied": True,
                    "tenant": tenant,
                    "source_of_truth": "sqlite/postgresql tenant-aware",
                    "scan_mode": "explicit_missing_text_backfill",
                    "idle": idle,
                    "last_scan": last_scan,
                    "totals": totals,
                    "cycles": cycles,
                },
            )
        if not until_idle:
            break
        if pause_seconds > 0:
            time.sleep(pause_seconds)
    if until_idle and not idle:
        groups, scan = _select_missing_sources(
            repo=repo,
            paths=dict(paths),
            limit=max(1, limit),
            include_archived=include_archived,
            exclude_source_keys=set(),
        )
        last_scan = dict(scan)
        idle = int(scan.get("processable_missing_text") or 0) == 0 and not groups
    result = {
        "ok": bool(totals["errors"] == 0 and (idle if until_idle else True)),
        "completed": True,
        "tenant": tenant,
        "source_of_truth": "sqlite/postgresql tenant-aware",
        "scan_mode": "explicit_missing_text_backfill",
        "include_archived": include_archived,
        "limit": max(1, limit),
        "until_idle": until_idle,
        "idle": idle,
        "last_scan": last_scan,
        "totals": totals,
        "cycles": cycles,
    }
    if checkpoint_path is not None:
        _write_json_atomic(checkpoint_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rigenera il testo Document AI mancante per i documenti dei fascicoli."
    )
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", action="append", default=[], help="Tenant da processare; ripetibile.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--until-idle", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=0.0)
    parser.add_argument("--include-archived", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if not args.apply:
        result = {
            "ok": False,
            "applied": False,
            "source_of_truth": "sqlite/postgresql tenant-aware",
            "errors": ["Esecuzione non avviata: specificare --apply."],
        }
    else:
        manager = GestioneTenant(str(args.registry))
        tenants = list(args.tenant or []) or [studio.slug for studio in manager.lista()]
        reports = []
        for tenant in tenants:
            report = run_tenant_cycles(
                registry=Path(args.registry),
                tenant=_text(tenant),
                limit=max(1, int(args.limit or 25)),
                max_cycles=max(1, int(args.max_cycles or 1)),
                until_idle=bool(args.until_idle),
                pause_seconds=max(0.0, float(args.pause_seconds or 0.0)),
                include_archived=bool(args.include_archived),
                checkpoint_path=Path(args.output) if args.output and len(tenants) == 1 else None,
            )
            reports.append(report)
        result = _result_payload(tenants=reports, completed=True, applied=True)
    rendered = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        _write_json_atomic(Path(args.output), result)
    print(rendered)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
