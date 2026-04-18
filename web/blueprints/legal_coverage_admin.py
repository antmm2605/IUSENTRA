"""Blueprint admin per coverage pipeline, review draft e pubblicazione SQL."""

from __future__ import annotations

from typing import Any

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for, current_app

from pct.legal_coverage_pipeline import (
    approve_draft,
    build_dashboard_payload,
    publish_single_draft,
    reject_draft,
    save_draft,
)
from pct.legal_taxonomy_sql_generator import generate_sql
from web.blueprints.admin import superadmin_required
from web.services.legal_coverage_surface import build_generator, build_repository, build_legal_coverage_surface, run_action


legal_coverage_admin = Blueprint(
    "legal_coverage_admin",
    __name__,
    url_prefix="/admin/copertura-ai",
)


def _json_error(message: str, *, status: int = 200):
    return jsonify({"ok": False, "errore": message}), status


def _selected_tenant_slug() -> str:
    if request.is_json:
        body = request.get_json(silent=True) or {}
        return str(body.get("tenant_slug") or "").strip().lower()
    return str(request.values.get("tenant_slug") or request.args.get("tenant_slug") or "").strip().lower()


@legal_coverage_admin.get("")
@legal_coverage_admin.get("/")
@superadmin_required
def dashboard():
    tenant_slug = _selected_tenant_slug()
    payload = build_legal_coverage_surface(tenant_slug=tenant_slug)
    return render_template(
        "admin/legal_coverage_dashboard.html",
        payload=payload,
        tenant_slug=payload["runtime"].get("tenant_slug", ""),
    )


@legal_coverage_admin.post("/esegui/<string:action>")
@superadmin_required
def execute_action(action: str):
    tenant_slug = _selected_tenant_slug()
    try:
        result = run_action(
            action,
            limit=int(request.form.get("limit") or 20),
            tenant_slug=tenant_slug,
        )
        labels = {
            "audit": "Audit copertura aggiornato.",
            "gaps": "Gap queue rigenerata.",
            "drafts": "Draft generati correttamente.",
            "publish": "Publisher eseguito e database riallineato.",
        }
        flash(labels.get(action, "Operazione completata."), "success")
        if result:
            current_app.logger.info("Coverage action %s -> %s", action, result)
    except Exception as exc:
        current_app.logger.exception("Errore action coverage %s: %s", action, exc)
        flash(f"Errore durante l'azione {action}: {exc}", "danger")
    redirect_kwargs = {"tenant_slug": tenant_slug} if tenant_slug else {}
    return redirect(url_for("legal_coverage_admin.dashboard", **redirect_kwargs))


@legal_coverage_admin.get("/review")
@superadmin_required
def review_page():
    tenant_slug = _selected_tenant_slug()
    return render_template(
        "admin/legal_coverage_review.html",
        tenant_slug=tenant_slug,
    )


@legal_coverage_admin.get("/api/drafts")
@superadmin_required
def api_drafts():
    try:
        repository = build_repository(tenant_slug=_selected_tenant_slug())
        if not repository.ping():
            return jsonify([])
        return jsonify(repository.list_drafts())
    except Exception as exc:
        current_app.logger.exception("Errore api_drafts: %s", exc)
        return jsonify([])


@legal_coverage_admin.get("/api/drafts/<int:draft_id>")
@superadmin_required
def api_draft_detail(draft_id: int):
    try:
        repository = build_repository(tenant_slug=_selected_tenant_slug())
        row = repository.get_draft(draft_id)
        if not row:
            return _json_error("Draft non trovato.", status=404)
        spec_json = dict(row.get("spec_json") or {})
        payload: dict[str, Any] = dict(row)
        payload["spec_json"] = spec_json
        payload["validation_report_json"] = dict(row.get("validation_report_json") or {})
        payload["retrieval_examples_json"] = list(row.get("retrieval_examples_json") or [])
        payload["sql_preview"] = generate_sql(spec_json)
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_detail: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/save")
@superadmin_required
def api_draft_save(draft_id: int):
    try:
        body = request.get_json(force=True) or {}
        spec_json = body.get("spec_json")
        if not isinstance(spec_json, dict):
            return _json_error("spec_json non valido.", status=400)
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        validation = save_draft(repository, draft_id, spec_json)
        return jsonify({"ok": True, "validation": validation})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_save: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/approve")
@superadmin_required
def api_draft_approve(draft_id: int):
    try:
        body = request.get_json(silent=True) or {}
        reviewer = str(body.get("reviewer") or "superadmin")
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        approve_draft(repository, draft_id, reviewer)
        return jsonify({"ok": True})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_approve: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/reject")
@superadmin_required
def api_draft_reject(draft_id: int):
    try:
        body = request.get_json(silent=True) or {}
        reviewer = str(body.get("reviewer") or "superadmin")
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        reject_draft(repository, draft_id, reviewer)
        return jsonify({"ok": True})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_reject: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/publish")
@superadmin_required
def api_draft_publish(draft_id: int):
    try:
        body = request.get_json(silent=True) or {}
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        draft = repository.get_draft(draft_id)
        if not draft:
            return _json_error("Draft non trovato.", status=404)
        repository.set_draft_status(draft_id, "approved", "review-ui")
        result = publish_single_draft(repository, draft_id, apply_to_db=True)
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_publish: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.get("/api/drafts/<int:draft_id>/sql")
@superadmin_required
def api_draft_sql(draft_id: int):
    try:
        repository = build_repository(tenant_slug=_selected_tenant_slug())
        row = repository.get_draft(draft_id)
        if not row:
            return _json_error("Draft non trovato.", status=404)
        return jsonify({"sql": generate_sql(dict(row.get("spec_json") or {}))})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_sql: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/pipeline/genera")
@superadmin_required
def api_generate_pipeline():
    try:
        tenant_slug = _selected_tenant_slug()
        repository = build_repository(tenant_slug=tenant_slug)
        generator = build_generator()
        payload = {
            "audit": run_action("audit", tenant_slug=tenant_slug),
            "gaps": run_action("gaps", tenant_slug=tenant_slug),
            "drafts": run_action(
                "drafts",
                limit=int((request.get_json(silent=True) or {}).get("limit") or 20),
                tenant_slug=tenant_slug,
            ),
            "dashboard": build_dashboard_payload(repository),
        }
        current_app.logger.info("Coverage pipeline refresh completato con modello %s", generator.ollama_model)
        return jsonify({"ok": True, "payload": payload})
    except Exception as exc:
        current_app.logger.exception("Errore api_generate_pipeline: %s", exc)
        return _json_error(str(exc))
