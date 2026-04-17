"""Orchestrazione audit -> gap -> draft -> review -> publish della coverage pipeline."""

from __future__ import annotations

from typing import Any

from pct.legal_coverage_ai import CoverageAutofillEngine
from pct.legal_coverage_defaults import (
    COVERAGE_SCORING,
    can_auto_publish,
    coverage_status_from_score,
    gap_type_from_missing_blocks,
    normalize_validation_status,
    priority_score_for_gap,
)
from pct.legal_taxonomy_sql_generator import generate_sql, validate_spec


def run_coverage_audit(repository: Any) -> dict[str, Any]:
    repository.ensure_schema()
    snapshots: list[dict[str, Any]] = []
    for subbranch_code in repository.list_known_subbranches():
        block_state = repository.get_subbranch_block_state(subbranch_code)
        score = 0
        missing_blocks: list[str] = []
        for block_name, points in COVERAGE_SCORING.items():
            if int(block_state.get(block_name) or 0) > 0:
                score += points
            else:
                missing_blocks.append(block_name)
        snapshots.append(
            {
                "subbranch_code": subbranch_code,
                "coverage_score": score,
                "coverage_status": coverage_status_from_score(score),
                "missing_blocks": missing_blocks,
                "procedure_count": int(block_state.get("procedure") or 0),
            }
        )

    repository.replace_snapshots(snapshots)
    ready = sum(1 for row in snapshots if row["coverage_status"] == "READY")
    return {
        "subbranches_total": len(snapshots),
        "ready_total": ready,
        "partial_total": sum(1 for row in snapshots if row["coverage_status"] == "PARTIAL"),
        "empty_total": sum(1 for row in snapshots if row["coverage_status"] == "EMPTY"),
    }


def build_gap_queue(repository: Any) -> dict[str, Any]:
    repository.ensure_schema()
    gaps: list[dict[str, Any]] = []
    for snapshot in repository.list_latest_snapshots():
        missing_blocks = list(snapshot.get("missing_blocks_json") or [])
        procedure_count = int(snapshot.get("procedure_count") or 0)
        gap_type = gap_type_from_missing_blocks(procedure_count, missing_blocks)
        if int(snapshot.get("coverage_score") or 0) >= 100 and not missing_blocks:
            continue
        metadata = repository.get_subbranch_metadata(str(snapshot["subbranch_code"]))
        gaps.append(
            {
                "subbranch_code": snapshot["subbranch_code"],
                "gap_type": gap_type,
                "priority_score": priority_score_for_gap(
                    coverage_score=int(snapshot.get("coverage_score") or 0),
                    operational_priority=int(metadata.get("operational_priority") or 50),
                    telematic=bool(metadata.get("telematic")),
                    preset_available=bool(metadata.get("preset_available")),
                    specialist_without_preset=bool(metadata.get("specialist_without_preset")),
                    gap_type=gap_type,
                ),
                "gap_payload": {
                    "coverage_score": int(snapshot.get("coverage_score") or 0),
                    "coverage_status": snapshot.get("coverage_status"),
                    "missing_blocks": missing_blocks,
                    "procedure_count": procedure_count,
                    "metadata": metadata,
                },
                "status": "OPEN",
            }
        )

    repository.replace_gap_queue(gaps)
    return {
        "gap_total": len(gaps),
        "high_priority_total": sum(1 for row in gaps if row["priority_score"] >= 120),
    }


def generate_drafts(
    repository: Any,
    generator: CoverageAutofillEngine,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    repository.ensure_schema()
    created = 0
    auto_approved = 0
    for gap in repository.list_open_gaps(limit=limit):
        generated = generator.generate_draft(repository, gap)
        spec_json = generated["spec_json"]
        validation = generated["validation_report_json"]
        risk_level = str(generated["risk_level"] or "MEDIUM")
        policy = repository.get_policy(str(gap["subbranch_code"]), risk_level)
        status = normalize_validation_status(
            list(validation.get("errors") or []),
            list(validation.get("warnings") or []),
        )
        auto_publish_eligible = can_auto_publish(
            policy=policy,
            complexity_level=risk_level,
            validation_errors=list(validation.get("errors") or []),
            validation_score=int(validation.get("score") or 0),
            subbranch_code=str(gap["subbranch_code"]),
        )
        if auto_publish_eligible and status == "validated":
            status = "approved"
            auto_approved += 1

        repository.create_draft(
            {
                "subbranch_code": gap["subbranch_code"],
                "procedure_code": generated.get("procedure_code"),
                "draft_source": "AI",
                "prompt_used": generated["prompt_used"],
                "retrieval_examples": generated["retrieval_examples"],
                "spec_json": spec_json,
                "validation_report_json": validation,
                "status": status,
                "risk_level": risk_level,
                "auto_publish_eligible": auto_publish_eligible,
            }
        )
        repository.set_gap_status(int(gap["id"]), "GENERATED")
        created += 1

    return {"draft_total": created, "auto_approved_total": auto_approved}


def save_draft(repository: Any, draft_id: int, spec_json: dict[str, Any]) -> dict[str, Any]:
    validation = validate_spec(spec_json, strict=False)
    status = normalize_validation_status(
        list(validation.get("errors") or []),
        list(validation.get("warnings") or []),
    )
    repository.update_draft_spec(draft_id, spec_json, validation, status)
    return validation


def approve_draft(repository: Any, draft_id: int, reviewer: str) -> None:
    repository.set_draft_status(draft_id, "approved", reviewer)


def reject_draft(repository: Any, draft_id: int, reviewer: str) -> None:
    repository.set_draft_status(draft_id, "rejected", reviewer)


def publish_approved_drafts(
    repository: Any,
    *,
    limit: int = 20,
    auto_only: bool = False,
    apply_to_db: bool = True,
) -> dict[str, Any]:
    repository.ensure_schema()
    published = 0
    learning_events = 0
    for draft in repository.list_publishable_drafts(limit=limit, auto_only=auto_only):
        spec_json = dict(draft.get("spec_json") or {})
        sql_payload = generate_sql(spec_json)
        if apply_to_db:
            repository.apply_generated_sql(sql_payload)
        history_id = repository.mark_published(
            int(draft["id"]),
            str(draft["subbranch_code"]),
            str(draft["procedure_code"]),
            sql_payload,
            "SQL",
        )
        repository.record_learning_event(
            history_id,
            str(draft["subbranch_code"]),
            str(draft["procedure_code"]),
            {
                "name": str((spec_json.get("procedure") or {}).get("name") or draft["procedure_code"]),
                "channel_code": str((spec_json.get("procedure") or {}).get("channel_code") or ""),
                "complexity_level": str((spec_json.get("procedure") or {}).get("complexity_level") or ""),
            },
        )
        published += 1
        learning_events += 1

    if published:
        run_coverage_audit(repository)
        build_gap_queue(repository)
    return {"published_total": published, "learning_events_total": learning_events}


def publish_single_draft(repository: Any, draft_id: int, *, apply_to_db: bool = True) -> dict[str, Any]:
    repository.ensure_schema()
    draft = repository.get_draft(draft_id)
    if not draft:
        raise ValueError("Draft non trovato.")
    if draft.get("status") != "approved":
        raise ValueError("Il draft deve essere approvato prima della pubblicazione.")

    spec_json = dict(draft.get("spec_json") or {})
    sql_payload = generate_sql(spec_json)
    if apply_to_db:
        repository.apply_generated_sql(sql_payload)
    history_id = repository.mark_published(
        int(draft["id"]),
        str(draft["subbranch_code"]),
        str(draft["procedure_code"]),
        sql_payload,
        "SQL",
    )
    repository.record_learning_event(
        history_id,
        str(draft["subbranch_code"]),
        str(draft["procedure_code"]),
        {
            "name": str((spec_json.get("procedure") or {}).get("name") or draft["procedure_code"]),
            "channel_code": str((spec_json.get("procedure") or {}).get("channel_code") or ""),
            "complexity_level": str((spec_json.get("procedure") or {}).get("complexity_level") or ""),
        },
    )
    run_coverage_audit(repository)
    build_gap_queue(repository)
    return {"published_total": 1, "learning_events_total": 1, "history_id": history_id}


def build_dashboard_payload(repository: Any) -> dict[str, Any]:
    repository.ensure_schema()
    snapshots = repository.list_latest_snapshots()
    drafts = repository.list_drafts()
    history = repository.list_published_history(limit=10)
    open_gaps = repository.list_open_gaps(limit=20)
    ready_total = sum(1 for row in snapshots if row.get("coverage_status") == "READY")
    average_score = (
        round(sum(int(row.get("coverage_score") or 0) for row in snapshots) / len(snapshots))
        if snapshots
        else 0
    )
    return {
        "headline": {
            "coverage_medio": average_score,
            "subbranch_ready": ready_total,
            "subbranch_parziali": sum(1 for row in snapshots if row.get("coverage_status") == "PARTIAL"),
            "gap_aperti": len(open_gaps),
            "draft_review": sum(1 for row in drafts if row.get("status") in {"generated", "validated", "needs_review"}),
            "training_implicito": repository.count_learning_events(),
        },
        "snapshots": snapshots,
        "gaps": open_gaps,
        "drafts": drafts,
        "history": history,
    }
