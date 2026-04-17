"""Superficie admin e wiring runtime per la coverage pipeline legale."""

from __future__ import annotations

from typing import Any

from flask import current_app

from pct.legal_coverage_ai import CoverageAutofillEngine, load_presets
from pct.legal_coverage_pipeline import (
    build_dashboard_payload,
    build_gap_queue,
    generate_drafts,
    publish_approved_drafts,
    run_coverage_audit,
)
from pct.legal_coverage_repository import CoverageDbConfig, PostgresCoverageRepository


def build_repository(app: Any | None = None) -> PostgresCoverageRepository:
    cfg_source = (app or current_app)._get_current_object().config if app or current_app else {}
    return PostgresCoverageRepository(CoverageDbConfig.from_mapping(cfg_source))


def build_generator(app: Any | None = None) -> CoverageAutofillEngine:
    source = (app or current_app)._get_current_object().config if app or current_app else {}
    return CoverageAutofillEngine(
        ollama_url=str(source.get("LOCAL_AI_BASE_URL") or source.get("PCT_LOCAL_AI_BASE_URL") or "").strip(),
        ollama_model=str(source.get("LOCAL_AI_CHAT_MODEL") or source.get("OLLAMA_MODEL") or "mistral").strip(),
        presets=load_presets(),
    )


def build_legal_coverage_surface(app: Any | None = None) -> dict[str, Any]:
    repository = build_repository(app)
    runtime = {
        "db_configured": repository.config.configured,
        "db_online": repository.ping(),
        "ollama_url": str((app or current_app).config.get("LOCAL_AI_BASE_URL") or ""),
        "ollama_model": str((app or current_app).config.get("LOCAL_AI_CHAT_MODEL") or (app or current_app).config.get("OLLAMA_MODEL") or ""),
    }
    if not runtime["db_online"]:
        return {
            "runtime": runtime,
            "headline": {
                "coverage_medio": 0,
                "subbranch_ready": 0,
                "subbranch_parziali": 0,
                "gap_aperti": 0,
                "draft_review": 0,
                "training_implicito": 0,
            },
            "snapshots": [],
            "gaps": [],
            "drafts": [],
            "history": [],
        }

    payload = build_dashboard_payload(repository)
    payload["runtime"] = runtime
    return payload


def run_action(action: str, *, limit: int = 20) -> dict[str, Any]:
    repository = build_repository()
    if not repository.ping():
        raise RuntimeError("Database coverage non raggiungibile.")

    if action == "audit":
        return run_coverage_audit(repository)
    if action == "gaps":
        return build_gap_queue(repository)
    if action == "drafts":
        return generate_drafts(repository, build_generator(), limit=limit)
    if action == "publish":
        return publish_approved_drafts(repository, limit=limit, apply_to_db=True)
    raise ValueError(f"Azione non supportata: {action}")
