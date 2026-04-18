from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from web.blueprints.admin import superadmin_required
from web.services.legal_update_surface import build_legal_update_pipeline_runtime, build_legal_update_surface, run_legal_update_action


legal_updates_admin = Blueprint(
    "legal_updates_admin",
    __name__,
    url_prefix="/admin/aggiornamenti-legali",
)


def _json_error(message: str, *, status: int = 200):
    return jsonify({"ok": False, "errore": message}), status


def _reviewer_name() -> str:
    user = getattr(g, "utente_corrente", None)
    return str(getattr(user, "username", "") or "superadmin")


@legal_updates_admin.get("")
@legal_updates_admin.get("/")
@superadmin_required
def dashboard():
    return render_template("admin/legal_updates_dashboard.html", payload=build_legal_update_surface())


@legal_updates_admin.post("/esegui/<string:action>")
@superadmin_required
def execute_action(action: str):
    try:
        result = run_legal_update_action(action)
        labels = {
            "scan": "Scansione fonti completata correttamente.",
            "autopublish": "Autopubblicazione news completata.",
        }
        flash(labels.get(action, "Operazione completata."), "success")
        current_app.logger.info("Legal updates action %s -> %s", action, result)
    except Exception as exc:
        current_app.logger.exception("Errore legal updates action %s: %s", action, exc)
        flash(f"Errore durante l'azione {action}: {exc}", "danger")
    return redirect(url_for("legal_updates_admin.dashboard"))


@legal_updates_admin.get("/review")
@superadmin_required
def review_page():
    pipeline = build_legal_update_pipeline_runtime()
    return render_template(
        "admin/legal_updates_review.html",
        review_items=pipeline.repository.list_review_queue(limit=100),
    )


@legal_updates_admin.post("/review/<int:review_id>/approve")
@superadmin_required
def approve(review_id: int):
    try:
        build_legal_update_pipeline_runtime().approve_review(
            review_id,
            reviewer=_reviewer_name(),
            notes=request.form.get("review_notes", ""),
        )
        flash("Proposta approvata.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore approve review %s: %s", review_id, exc)
        flash(f"Errore approvazione: {exc}", "danger")
    return redirect(url_for("legal_updates_admin.review_page"))


@legal_updates_admin.post("/review/<int:review_id>/reject")
@superadmin_required
def reject(review_id: int):
    try:
        build_legal_update_pipeline_runtime().reject_review(
            review_id,
            reviewer=_reviewer_name(),
            notes=request.form.get("review_notes", ""),
        )
        flash("Proposta rifiutata.", "warning")
    except Exception as exc:
        current_app.logger.exception("Errore reject review %s: %s", review_id, exc)
        flash(f"Errore rifiuto: {exc}", "danger")
    return redirect(url_for("legal_updates_admin.review_page"))


@legal_updates_admin.post("/review/<int:review_id>/publish")
@superadmin_required
def publish(review_id: int):
    try:
        build_legal_update_pipeline_runtime().publish_review(review_id, reviewer=_reviewer_name())
        flash("Contenuto pubblicato correttamente.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore publish review %s: %s", review_id, exc)
        flash(f"Errore pubblicazione: {exc}", "danger")
    return redirect(url_for("legal_updates_admin.review_page"))


@legal_updates_admin.get("/api/review-queue")
@superadmin_required
def api_review_queue():
    try:
        pipeline = build_legal_update_pipeline_runtime()
        return jsonify({"ok": True, "items": pipeline.repository.list_review_queue(limit=100)})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_queue: %s", exc)
        return _json_error(str(exc))


@legal_updates_admin.get("/api/review-queue/<int:review_id>")
@superadmin_required
def api_review_detail(review_id: int):
    try:
        pipeline = build_legal_update_pipeline_runtime()
        row = pipeline.repository.get_review_item(review_id)
        if not row:
            return _json_error("Review non trovata.", status=404)
        return jsonify({"ok": True, "item": row})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_detail: %s", exc)
        return _json_error(str(exc))


@legal_updates_admin.post("/api/review-queue/<int:review_id>/approve")
@superadmin_required
def api_review_approve(review_id: int):
    try:
        reviewer = str((request.get_json(silent=True) or {}).get("reviewer") or "superadmin")
        notes = str((request.get_json(silent=True) or {}).get("review_notes") or "")
        row = build_legal_update_pipeline_runtime().approve_review(review_id, reviewer=reviewer, notes=notes)
        return jsonify({"ok": True, "item": row})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_approve: %s", exc)
        return _json_error(str(exc))


@legal_updates_admin.post("/api/review-queue/<int:review_id>/reject")
@superadmin_required
def api_review_reject(review_id: int):
    try:
        reviewer = str((request.get_json(silent=True) or {}).get("reviewer") or "superadmin")
        notes = str((request.get_json(silent=True) or {}).get("review_notes") or "")
        row = build_legal_update_pipeline_runtime().reject_review(review_id, reviewer=reviewer, notes=notes)
        return jsonify({"ok": True, "item": row})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_reject: %s", exc)
        return _json_error(str(exc))


@legal_updates_admin.post("/api/review-queue/<int:review_id>/publish")
@superadmin_required
def api_review_publish(review_id: int):
    try:
        reviewer = str((request.get_json(silent=True) or {}).get("reviewer") or "superadmin")
        result = build_legal_update_pipeline_runtime().publish_review(review_id, reviewer=reviewer)
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        current_app.logger.exception("Errore api_review_publish: %s", exc)
        return _json_error(str(exc))


@legal_updates_admin.get("/api/sources")
@superadmin_required
def api_sources():
    try:
        pipeline = build_legal_update_pipeline_runtime()
        return jsonify({"ok": True, "items": pipeline.list_sources(enabled_only=False)})
    except Exception as exc:
        current_app.logger.exception("Errore api_sources: %s", exc)
        return _json_error(str(exc))


@legal_updates_admin.get("/api/news")
@superadmin_required
def api_news():
    try:
        pipeline = build_legal_update_pipeline_runtime()
        return jsonify({"ok": True, "items": pipeline.repository.list_news(limit=100, include_drafts=True)})
    except Exception as exc:
        current_app.logger.exception("Errore api_news admin: %s", exc)
        return _json_error(str(exc))
