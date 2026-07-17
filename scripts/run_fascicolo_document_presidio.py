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


def _outcome_summary(value: Any) -> dict[str, Any]:
    item = dict(value) if isinstance(value, dict) else {}
    deadline = item.get("deadline") if isinstance(item.get("deadline"), dict) else {}
    activity = item.get("activity") if isinstance(item.get("activity"), dict) else {}
    return {
        "status": _text(item.get("status")),
        "fascicolo_id": _text(item.get("fascicolo_id")),
        "document": _text(item.get("document")),
        "due_date": _text(item.get("due_date")),
        "kind": _text(item.get("kind")),
        "reason": _text(item.get("reason")),
        "deadline": {
            "ok": bool(deadline.get("ok")),
            "message": _text(deadline.get("message")),
            "deadline_id": _text(deadline.get("deadline_id")),
            "expired": bool(deadline.get("expired")),
        },
        "activity": {
            "ok": bool(activity.get("ok")),
            "created": bool(activity.get("created")),
            "activity_id": _text(activity.get("activity_id")),
            "message": _text(activity.get("message")),
        },
    }


def _result_payload(
    *,
    tenant: str,
    limit: int,
    until_idle: bool,
    idle: bool,
    completed: bool,
    mirror_regenerated: bool,
    totals: dict[str, int],
    cycles: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ok": bool(completed and totals["errors"] == 0 and (idle if until_idle else True)),
        "completed": completed,
        "tenant": tenant,
        "source_of_truth": "sqlite",
        "scan_mode": "incremental_new_or_changed_only",
        "limit": max(1, limit),
        "until_idle": until_idle,
        "idle": idle,
        "mirror_regenerated": mirror_regenerated,
        "totals": dict(totals),
        "cycles": list(cycles),
    }


def run_cycles(
    *,
    registry: Path,
    tenant: str,
    limit: int,
    max_cycles: int,
    until_idle: bool,
    pause_seconds: float,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    manager = GestioneTenant(str(registry))
    studios = [studio for studio in manager.lista() if studio.slug.casefold() == tenant.casefold()]
    if not studios:
        return {"ok": False, "source_of_truth": "missing", "errors": [f"Studio non trovato: {tenant}"]}
    paths = manager.percorsi_dati(tenant, reconcile_aliases=False, ensure_baseline=False)
    repo = repository_from_paths(paths, tenant_label=tenant)
    cycles: list[dict[str, Any]] = []
    totals = {
        "cycles": 0,
        "processed_new_documents": 0,
        "indexed_documents": 0,
        "indexing_skipped": 0,
        "candidate_dates": 0,
        "scheduled": 0,
        "already_presided": 0,
        "past_remote_hearings_recorded": 0,
        "skipped_non_blocking_documents": 0,
        "skipped": 0,
        "persisted_activity_fascicoli": 0,
        "errors": 0,
    }
    idle = False
    for cycle in range(1, max(1, max_cycles) + 1):
        started = time.monotonic()

        def checkpoint_progress(progress: dict[str, Any]) -> None:
            if checkpoint_path is None:
                return
            partial = _result_payload(
                tenant=tenant,
                limit=limit,
                until_idle=until_idle,
                idle=False,
                completed=False,
                mirror_regenerated=False,
                totals=totals,
                cycles=cycles,
            )
            partial["current"] = {"cycle": cycle, **dict(progress or {})}
            _write_json_atomic(checkpoint_path, partial)

        report = repo.recover_missing_hearings_from_fascicolo_documents(
            limit=max(1, limit),
            actor="document-presidio-backfill",
            regenerate_mirror=False,
            progress_callback=checkpoint_progress,
        )
        elapsed = round(time.monotonic() - started, 3)
        errors = list(report.get("errors") or []) + list(report.get("transient_errors") or [])
        item = {
            "cycle": cycle,
            "elapsed_seconds": elapsed,
            "processed_new_documents": int(report.get("processed_new_documents") or 0),
            "indexed_documents": int(report.get("indexed_documents") or 0),
            "indexing_skipped": int(report.get("indexing_skipped") or 0),
            "candidate_dates": int(report.get("candidate_dates") or 0),
            "scheduled": int(report.get("scheduled") or 0),
            "already_presided": int(report.get("already_presided") or 0),
            "past_remote_hearings_recorded": int(report.get("past_remote_hearings_recorded") or 0),
            "skipped_non_blocking_documents": int(report.get("skipped_non_blocking_documents") or 0),
            "skipped": int(report.get("skipped") or 0),
            "persisted_activity_fascicoli": int(report.get("persisted_activity_fascicoli") or 0),
            "pending_fascicoli": int(report.get("pending_fascicoli") or 0),
            "pending_documents": int(report.get("pending_new_or_changed_documents") or 0),
            "errors": errors[:20],
            "outcomes": [
                _outcome_summary(value)
                for value in list(report.get("items") or [])[:30]
            ],
        }
        cycles.append(item)
        totals["cycles"] += 1
        for key in (
            "processed_new_documents",
            "indexed_documents",
            "indexing_skipped",
            "candidate_dates",
            "scheduled",
            "already_presided",
            "past_remote_hearings_recorded",
            "skipped_non_blocking_documents",
            "skipped",
            "persisted_activity_fascicoli",
        ):
            totals[key] += int(item[key])
        totals["errors"] += len(errors)
        idle = (
            item["processed_new_documents"] == 0
            and item["pending_fascicoli"] == 0
            and item["pending_documents"] == 0
            and not errors
        )
        if checkpoint_path is not None:
            _write_json_atomic(
                checkpoint_path,
                _result_payload(
                    tenant=tenant,
                    limit=limit,
                    until_idle=until_idle,
                    idle=idle,
                    completed=False,
                    mirror_regenerated=False,
                    totals=totals,
                    cycles=cycles,
                ),
            )
        if not until_idle or idle:
            break
        if pause_seconds > 0:
            time.sleep(pause_seconds)
    mirror_regenerated = False
    if totals["persisted_activity_fascicoli"]:
        repo._fascicoli_manager()._rigenera_mirror_fascicoli_json()
        mirror_regenerated = True
    result = _result_payload(
        tenant=tenant,
        limit=limit,
        until_idle=until_idle,
        idle=idle,
        completed=True,
        mirror_regenerated=mirror_regenerated,
        totals=totals,
        cycles=cycles,
    )
    if checkpoint_path is not None:
        _write_json_atomic(checkpoint_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Esegue il presidio documentale incrementale tenant-aware.")
    parser.add_argument("--registry", default="data/tenants.json")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--max-cycles", type=int, default=1)
    parser.add_argument("--until-idle", action="store_true")
    parser.add_argument("--pause-seconds", type=float, default=0.0)
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
        result = run_cycles(
            registry=Path(args.registry),
            tenant=_text(args.tenant),
            limit=max(1, int(args.limit or 25)),
            max_cycles=max(1, int(args.max_cycles or 1)),
            until_idle=bool(args.until_idle),
            pause_seconds=max(0.0, float(args.pause_seconds or 0.0)),
            checkpoint_path=Path(args.output) if args.output else None,
        )
        result["applied"] = True
    rendered = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        output = Path(args.output)
        _write_json_atomic(output, result)
    print(rendered)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
