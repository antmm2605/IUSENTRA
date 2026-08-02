"""Blueprint admin per crash test operativo e backup blindato."""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from web.blueprints.admin import superadmin_required
from web.services.operational_resilience_surface import (
    build_operational_crash_surface,
    execute_operational_backup_surface,
    execute_operational_crash_surface,
)


operational_resilience_admin = Blueprint(
    "operational_resilience_admin",
    __name__,
    url_prefix="/admin/crash-test-operativo",
)


def _selected_slug() -> str:
    return str(request.values.get("slug", "") or "").strip().lower()


def _redirect_back() -> object:
    return redirect(url_for("operational_resilience_admin.dashboard", slug=_selected_slug()))


def _admin_json_response(payload: Any):
    return current_app.response_class(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        mimetype="application/json",
    )


@operational_resilience_admin.get("")
@superadmin_required
def dashboard():
    payload = build_operational_crash_surface(selected_slug=_selected_slug())
    return render_template("admin/crash_test_operativo.html", payload=payload)


@operational_resilience_admin.get("/api")
@superadmin_required
def api_dashboard():
    try:
        payload = build_operational_crash_surface(selected_slug=_selected_slug())
        return _admin_json_response(payload)
    except Exception as exc:  # pragma: no cover - difensivo UI
        current_app.logger.exception("Errore API resilienza operativa: %s", exc)
        return jsonify({"ok": False, "message": "Resilienza operativa non disponibile."}), 200


@operational_resilience_admin.post("/esegui")
@superadmin_required
def esegui():
    selected_slug = str(request.form.get("slug", "") or "").strip().lower()
    auto_repair = str(request.form.get("auto_repair", "1") or "1").strip().lower() not in {
        "0",
        "false",
        "off",
        "no",
    }
    max_attempts = int(str(request.form.get("max_attempts", "3") or "3").strip() or 3)
    try:
        report = execute_operational_crash_surface(
            selected_slug=selected_slug,
            trigger_source="manual",
            schedule_code="manual",
            auto_repair=auto_repair,
            max_attempts=max_attempts,
        )
        if report.get("overall_ok"):
            flash("Crash test operativo completato con esito verde.", "success")
        else:
            flash("Crash test operativo completato con criticita' tracciate e ticket di riparazione.", "warning")
        if report.get("report_path"):
            flash(f"Report generato: {report['report_path']}", "info")
    except Exception as exc:
        current_app.logger.exception("Errore crash test operativo: %s", exc)
        flash("Errore durante il crash test operativo.", "danger")
    return redirect(url_for("operational_resilience_admin.dashboard", slug=selected_slug))


@operational_resilience_admin.post("/backup")
@superadmin_required
def backup():
    selected_slug = str(request.form.get("slug", "") or "").strip().lower()
    try:
        report = execute_operational_backup_surface(
            selected_slug=selected_slug,
            trigger_source="manual",
            schedule_code="manual",
        )
        if report.get("skipped"):
            flash("Archivi e copie sono disattivati dalla politica operativa dello studio.", "info")
        elif report.get("success"):
            flash("Backup blindato completo e incrementale eseguito correttamente.", "success")
        else:
            flash("Backup blindato eseguito con errori: controlla il report operativo.", "warning")
        if report.get("report_path"):
            flash(f"Report backup: {report['report_path']}", "info")
    except Exception as exc:
        current_app.logger.exception("Errore backup blindato: %s", exc)
        flash("Errore durante il backup blindato.", "danger")
    return redirect(url_for("operational_resilience_admin.dashboard", slug=selected_slug))
