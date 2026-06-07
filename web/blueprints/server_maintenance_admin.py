"""Pannello Superadmin per server e manutenzione storage."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for

from web.blueprints.admin import superadmin_required
from web.services.server_maintenance_surface import (
    build_server_maintenance_surface,
    run_all_backup_retention,
    run_docker_prune,
    run_inactive_tenant_cleanup,
    run_max_storage_optimization,
    run_normativa_global_cleanup,
    run_professional_server_maintenance,
    run_system_log_cleanup,
    run_storage_compaction,
    trigger_backup,
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
        docker_prune=None,
        max_optimization=None,
        inactive_cleanup=None,
        professional_maintenance=None,
        log_cleanup=None,
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
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
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
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore compattazione storage: %s", exc)
        flash("Errore durante la compattazione storage.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/analizza-ottimizzazione-massima")
@superadmin_required
def analizza_ottimizzazione_massima():
    try:
        tenant_slug = str(request.form.get("tenant_slug", "") or "").strip()
        optimization = run_max_storage_optimization(apply=False, tenant_slug=tenant_slug)
        flash(
            "Analisi ottimizzazione completata: "
            f"spazio recuperabile {optimization['bytes_reclaimable_label']}.",
            "info",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=optimization,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi ottimizzazione storage: %s", exc)
        flash("Errore durante l'analisi ottimizzazione storage.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/applica-ottimizzazione-massima")
@superadmin_required
def applica_ottimizzazione_massima():
    try:
        tenant_slug = str(request.form.get("tenant_slug", "") or "").strip()
        optimization = run_max_storage_optimization(apply=True, tenant_slug=tenant_slug)
        flash(
            "Ottimizzazione completata: "
            f"recuperati {optimization['bytes_reclaimed_label']}.",
            "success",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=optimization,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore ottimizzazione storage: %s", exc)
        flash("Errore durante l'ottimizzazione storage.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/analizza-retention-backup")
@superadmin_required
def analizza_retention_backup():
    try:
        backup_retention = run_all_backup_retention(apply=False)
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
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi retention backup: %s", exc)
        flash("Errore durante l'analisi retention backup.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/applica-retention-backup")
@superadmin_required
def applica_retention_backup():
    try:
        backup_retention = run_all_backup_retention(apply=True)
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
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore retention backup: %s", exc)
        flash("Errore durante la retention backup.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/backup-ora")
@superadmin_required
def backup_ora():
    try:
        result = trigger_backup()
        if result["ok"]:
            flash(f"Backup avviato in background (PID {result['pid']}).", "success")
        else:
            flash(f"Errore avvio backup: {result['error']}", "danger")
    except Exception as exc:
        current_app.logger.exception("Errore avvio backup: %s", exc)
        flash("Errore durante l'avvio del backup.", "danger")
    return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/docker-prune")
@superadmin_required
def docker_prune():
    try:
        result = run_docker_prune(dry_run=False)
        if result.get("error"):
            flash(f"Pulizia cache servizi non completata: {result['error']}", "warning")
        else:
            flash(f"Pulizia cache servizi completata: recuperati {result['bytes_reclaimed_label']}.", "success")
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=result,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore docker prune: %s", exc)
        flash("Errore durante docker prune.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/analizza-cartelle-escluse")
@superadmin_required
def analizza_cartelle_escluse():
    try:
        cleanup = run_inactive_tenant_cleanup(apply=False)
        flash(
            "Analisi cartelle escluse completata: "
            f"{cleanup['candidates_count']} cartelle eliminabili, "
            f"spazio recuperabile {cleanup['bytes_reclaimable_label']}.",
            "info",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=cleanup,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi cartelle escluse: %s", exc)
        flash("Errore durante l'analisi delle cartelle escluse.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/elimina-cartelle-escluse")
@superadmin_required
def elimina_cartelle_escluse():
    try:
        cleanup = run_inactive_tenant_cleanup(apply=True)
        level = "warning" if cleanup.get("errors") else "success"
        flash(
            "Pulizia cartelle escluse completata: "
            f"{cleanup['directories_deleted']} cartelle rimosse, "
            f"recuperati {cleanup['bytes_reclaimed_label']}.",
            level,
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=cleanup,
            professional_maintenance=None,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore pulizia cartelle escluse: %s", exc)
        flash("Errore durante la pulizia delle cartelle escluse.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/analizza-manutenzione-professionale")
@superadmin_required
def analizza_manutenzione_professionale():
    try:
        maintenance = run_professional_server_maintenance(apply=False)
        flash(
            "Analisi manutenzione professionale completata: "
            f"spazio recuperabile {maintenance['bytes_reclaimable_label']}.",
            "info",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=maintenance,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi manutenzione professionale: %s", exc)
        flash("Errore durante l'analisi manutenzione professionale.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/applica-manutenzione-professionale")
@superadmin_required
def applica_manutenzione_professionale():
    try:
        maintenance = run_professional_server_maintenance(apply=True)
        level = "warning" if maintenance.get("errors") else "success"
        flash(
            "Manutenzione professionale completata: "
            f"recuperati {maintenance['bytes_reclaimed_label']}.",
            level,
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=maintenance,
            log_cleanup=None,
        )
    except Exception as exc:
        current_app.logger.exception("Errore manutenzione professionale: %s", exc)
        flash("Errore durante la manutenzione professionale.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/pulisci-log-sistema")
@superadmin_required
def pulisci_log_sistema():
    try:
        result = run_system_log_cleanup(apply=True)
        level = "warning" if result.get("errors") else "success"
        flash("Pulizia log sistema completata.", level)
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=result,
        )
    except Exception as exc:
        current_app.logger.exception("Errore pulizia log sistema: %s", exc)
        flash("Errore durante la pulizia dei log sistema.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/analizza-normativa-globale")
@superadmin_required
def analizza_normativa_globale():
    try:
        result = run_normativa_global_cleanup(apply=False)
        flash(
            "Analisi normativa globale completata: "
            f"backup duplicati recuperabili {result['bytes_reclaimable_label']}.",
            "info",
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
            normativa_cleanup=result,
        )
    except Exception as exc:
        current_app.logger.exception("Errore analisi normativa globale: %s", exc)
        flash("Errore durante l'analisi della normativa globale.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))


@server_maintenance_admin.post("/pulisci-normativa-globale")
@superadmin_required
def pulisci_normativa_globale():
    try:
        result = run_normativa_global_cleanup(apply=True)
        level = "warning" if result.get("errors") else "success"
        flash(
            "Pulizia normativa globale completata: "
            f"recuperati {result['bytes_reclaimed_label']}.",
            level,
        )
        return render_template(
            "admin/server_manutenzione.html",
            payload=build_server_maintenance_surface(),
            compaction=None,
            backup_retention=None,
            docker_prune=None,
            max_optimization=None,
            inactive_cleanup=None,
            professional_maintenance=None,
            log_cleanup=None,
            normativa_cleanup=result,
        )
    except Exception as exc:
        current_app.logger.exception("Errore pulizia normativa globale: %s", exc)
        flash("Errore durante la pulizia della normativa globale.", "danger")
        return redirect(url_for("server_maintenance_admin.dashboard"))
