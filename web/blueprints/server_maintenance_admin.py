"""Pannello Superadmin per server e manutenzione storage."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from web.blueprints.admin import superadmin_required
from web.services.server_maintenance_surface import (
    build_server_maintenance_surface,
    run_backup_retention,
    run_storage_compaction,
)


server_maintenance_admin = Blueprint(
    "server_maintenance_admin",
    __name__,
    url_prefix="/admin/server-manutenzione",
)


@server_maintenance_admin.get("")
@superadmin_required
def dashboard():
    payload = build_server_maintenance_surface()
    return render_template(
        "admin/server_manutenzione.html",
        payload=payload,
        compaction=None,
        backup_retention=None,
    )


@server_maintenance_admin.get("/api")
@superadmin_required
def api_dashboard():
    return jsonify(build_server_maintenance_surface())


@server_maintenance_admin.post("/analizza-compattazione")
@superadmin_required
def analizza_compattazione():
    try:
        tenant_slug = str(request.form.get("tenant_slug", "") or "").strip()
        compaction = run_storage_compaction(apply=False, tenant_slug=tenant_slug)
        physical_duplicates = int(compaction.get("physical_duplicate_files", 0) or 0)
        flash(
            "Analisi compattazione completata: "
            f"{physical_duplicates} file da compattare, "
            f"spazio recuperabile {compaction['bytes_reclaimable_label']}.",
            "info",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=compaction,
            backup_retention=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi compattazione storage: %s", exc)
        flash("Errore durante l'analisi compattazione storage.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/compatta")
@superadmin_required
def compatta():
    try:
        tenant_slug = str(request.form.get("tenant_slug", "") or "").strip()
        compaction = run_storage_compaction(apply=True, tenant_slug=tenant_slug)
        hardlinked_files = int(compaction.get("hardlinked_files", 0) or 0)
        flash(
            "Compattazione completata: "
            f"{hardlinked_files} file compattati ora, "
            f"recuperati {compaction['bytes_reclaimed_label']}.",
            "success",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=compaction,
            backup_retention=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore compattazione storage: %s", exc)
        flash("Errore durante la compattazione storage.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/analizza-retention-backup")
@superadmin_required
def analizza_retention_backup():
    try:
        backup_retention = run_backup_retention(apply=False)
        flash(
            "Analisi retention backup completata: "
            f"{backup_retention['archives_to_delete']} archivi eliminabili, "
            f"spazio recuperabile {backup_retention['bytes_reclaimable_label']}.",
            "info",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=backup_retention,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi retention backup: %s", exc)
        flash("Errore durante l'analisi retention backup.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/applica-retention-backup")
@superadmin_required
def applica_retention_backup():
    try:
        backup_retention = run_backup_retention(apply=True)
        level = "warning" if backup_retention.get("errors") else "success"
        flash(
            "Retention backup applicata: "
            f"{backup_retention['archives_deleted']} archivi rimossi, "
            f"recuperati {backup_retention['bytes_reclaimed_label']}.",
            level,
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=backup_retention,
        )
    except Exception as exc:
        current_app.logger.exception("Errore retention backup: %s", exc)
        flash("Errore durante la retention backup.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))
