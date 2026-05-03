"""Blueprint admin per coverage pipeline, review draft e pubblicazione SQL."""

from __future__ import annotations

from functools import wraps
from typing import Any

from flask import Blueprint, abort, flash, g, jsonify, redirect, render_template, request, url_for, current_app

from pct.auth import RuoloUtente
from pct.legal_coverage_pipeline import (
    approve_draft,
    build_dashboard_payload,
    publish_single_draft,
    reject_draft,
    save_draft,
)
from pct.legal_taxonomy_sql_generator import generate_sql
from web.services.legal_coverage_surface import build_generator, build_repository, build_legal_coverage_surface, run_action


legal_coverage_admin = Blueprint(
    "legal_coverage_admin",
    __name__,
    url_prefix="/admin/copertura-ai",
)


def coverage_admin_required(fn):
    """Consente SUPERADMIN oppure admin locale quando il runtime non e' multi-tenant."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = getattr(g, "utente_corrente", None)
        if not user:
            abort(403)
        if getattr(user, "is_superadmin", False):
            return fn(*args, **kwargs)
        multi_tenant = bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False))
        if not multi_tenant and getattr(user, "ruolo", None) == RuoloUtente.AMMINISTRATORE:
            return fn(*args, **kwargs)
        abort(403)

    return wrapper


def _json_error(message: str, *, status: int = 200):
    return jsonify({"ok": False, "errore": message}), status


def _selected_tenant_slug() -> str:
    if request.is_json:
        body = request.get_json(silent=True) or {}
        return str(body.get("tenant_slug") or "").strip().lower()
    return str(request.values.get("tenant_slug") or request.args.get("tenant_slug") or "").strip().lower()


def _review_payload(required_reason: bool = False) -> tuple[dict[str, Any], str, str, str]:
    body = request.get_json(silent=True) or {}
    reviewer = str(body.get("reviewer") or "superadmin").strip()
    review_reason = str(body.get("review_reason") or "").strip()
    review_signature = str(body.get("review_signature") or "").strip()
    if required_reason and not review_reason:
        raise ValueError("Inserisci il motivo della decisione prima di continuare.")
    if not review_signature:
        raise ValueError("Inserisci la firma del reviewer per chiudere la revisione.")
    return body, reviewer, review_reason, review_signature


@legal_coverage_admin.get("")
@legal_coverage_admin.get("/")
@coverage_admin_required
def dashboard():
    tenant_slug = _selected_tenant_slug()
    payload = build_legal_coverage_surface(tenant_slug=tenant_slug)
    return render_template(
        "admin/legal_coverage_dashboard.html",
        payload=payload,
        tenant_slug=payload["runtime"].get("tenant_slug", ""),
    )


@legal_coverage_admin.post("/esegui/<string:action>")
@coverage_admin_required
def execute_action(action: str):
    tenant_slug = _selected_tenant_slug()
    try:
        result = run_action(
            action,
            limit=int(request.form.get("limit") or 20),
            tenant_slug=tenant_slug,
        )
        category = "success"
        message = {
            "audit": "Audit copertura aggiornato.",
            "gaps": "Gap queue rigenerata.",
            "drafts": "Draft generati correttamente.",
            "publish": "Publisher eseguito e database riallineato.",
        }.get(action, "Operazione completata.")
        if action == "drafts":
            generated = int((result or {}).get("draft_total") or 0)
            skipped = int((result or {}).get("skipped_pending_review_total") or 0)
            if generated == 0 and skipped:
                category = "warning"
                message = "Le bozze erano gia' in revisione: nessuna duplicazione generata."
        if action == "publish" and int((result or {}).get("published_total") or 0) == 0:
            category = "warning"
            message = "Nessuna bozza approvata da pubblicare. Apri la coda revisioni, approva una bozza e ripeti il publish."
        flash(message, category)
        if result:
            current_app.logger.info("Coverage action %s -> %s", action, result)
    except Exception as exc:
        current_app.logger.exception("Errore action coverage %s: %s", action, exc)
        flash(f"Errore durante l'azione {action}: {exc}", "danger")
    redirect_kwargs = {"tenant_slug": tenant_slug} if tenant_slug else {}
    return redirect(url_for("legal_coverage_admin.dashboard", **redirect_kwargs))


@legal_coverage_admin.get("/review")
@coverage_admin_required
def review_page():
    tenant_slug = _selected_tenant_slug()
    return render_template(
        "admin/legal_coverage_review.html",
        tenant_slug=tenant_slug,
    )


@legal_coverage_admin.get("/api/drafts")
@coverage_admin_required
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
@coverage_admin_required
def api_draft_detail(draft_id: int):
    try:
        repository = build_repository(tenant_slug=_selected_tenant_slug())
        row = repository.get_draft(draft_id)
        if not row:
            return _json_error("Draft non trovato.", status=404)
        spec_json = dict(row.get("spec_json") or {})
        payload: dict[str, Any] = dict(row)
        payload["spec_json"] = spec_json
        payload["draft_spec_original_json"] = dict(row.get("draft_spec_original_json") or {})
        payload["validation_report_json"] = dict(row.get("validation_report_json") or {})
        payload["retrieval_examples_json"] = list(row.get("retrieval_examples_json") or [])
        payload["review_diff_json"] = dict(row.get("review_diff_json") or {})
        payload["review_history"] = repository.list_review_history(draft_id)
        risk_level = str(row.get("risk_level") or "MEDIUM").strip().upper()
        payload["autopublish_policy"] = repository.get_policy(
            str(row.get("subbranch_code") or ""),
            risk_level,
        )
        payload["ai_governance"] = {
            "draft_source": str(row.get("draft_source") or "AI"),
            "risk_level": risk_level,
            "auto_publish_eligible": bool(row.get("auto_publish_eligible")),
            "review_required": not bool(row.get("auto_publish_eligible")) or str(row.get("status") or "") not in {"approved", "published"},
            "reviewer": str(row.get("reviewer") or ""),
            "review_signature": str(row.get("review_signature") or ""),
            "review_reason": str(row.get("review_reason") or ""),
            "decision": str(row.get("last_review_action") or ""),
        }
        payload["sql_preview"] = generate_sql(spec_json)
        return jsonify(payload)
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_detail: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/save")
@coverage_admin_required
def api_draft_save(draft_id: int):
    try:
        body = request.get_json(force=True) or {}
        spec_json = body.get("spec_json")
        if not isinstance(spec_json, dict):
            return _json_error("spec_json non valido.", status=400)
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        validation = save_draft(
            repository,
            draft_id,
            spec_json,
            reviewer=str(body.get("reviewer") or "review-ui").strip(),
            review_signature=str(body.get("review_signature") or "").strip(),
        )
        return jsonify({"ok": True, "validation": validation})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_save: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/approve")
@coverage_admin_required
def api_draft_approve(draft_id: int):
    try:
        body, reviewer, review_reason, review_signature = _review_payload(required_reason=True)
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        approve_draft(
            repository,
            draft_id,
            reviewer,
            review_reason=review_reason,
            review_signature=review_signature,
        )
        return jsonify({"ok": True})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_approve: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/reject")
@coverage_admin_required
def api_draft_reject(draft_id: int):
    try:
        body, reviewer, review_reason, review_signature = _review_payload(required_reason=True)
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        reject_draft(
            repository,
            draft_id,
            reviewer,
            review_reason=review_reason,
            review_signature=review_signature,
        )
        return jsonify({"ok": True})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_reject: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.post("/api/drafts/<int:draft_id>/publish")
@coverage_admin_required
def api_draft_publish(draft_id: int):
    try:
        body, reviewer, review_reason, review_signature = _review_payload(required_reason=False)
        repository = build_repository(tenant_slug=str(body.get("tenant_slug") or _selected_tenant_slug()).strip().lower())
        draft = repository.get_draft(draft_id)
        if not draft:
            return _json_error("Draft non trovato.", status=404)
        if draft.get("status") != "approved":
            repository.set_draft_status(
                draft_id,
                "approved",
                reviewer or "review-ui",
                review_reason=review_reason or str(draft.get("review_reason") or ""),
                review_signature=review_signature or str(draft.get("review_signature") or ""),
            )
        result = publish_single_draft(repository, draft_id, apply_to_db=True)
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_draft_publish: %s", exc)
        return _json_error(str(exc))


@legal_coverage_admin.get("/api/drafts/<int:draft_id>/sql")
@coverage_admin_required
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
@coverage_admin_required
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
