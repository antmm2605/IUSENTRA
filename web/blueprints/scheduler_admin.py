"""Console superadmin per pianificazioni, cronjob e agenti delegati."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for, g

from web.blueprints.admin import superadmin_required
from web.services.scheduler_admin_surface import (
    build_scheduler_admin_surface,
    cancel_legal_source_runs,
    create_scheduler_job_from_payload,
    request_scheduler_run,
    save_scheduler_job_from_payload,
)
from web.services.security_redaction import redacted_json_response


scheduler_admin = Blueprint("scheduler_admin", __name__)


def _username() -> str:
    user = getattr(g, "utente_corrente", None)
    return str(getattr(user, "username", "") or "superadmin")


@scheduler_admin.get("/admin/pianificazioni")
@superadmin_required
def dashboard():
    return render_template("admin/pianificazioni.html", payload=build_scheduler_admin_surface())


@scheduler_admin.get("/admin/cronjob")
@superadmin_required
def cronjob_alias():
    return redirect(url_for("scheduler_admin.dashboard"))


@scheduler_admin.get("/admin/pianificazioni/api")
@superadmin_required
def api_dashboard():
    return redacted_json_response(build_scheduler_admin_surface())


@scheduler_admin.post("/admin/pianificazioni/<string:job_id>/salva")
@superadmin_required
def save_job(job_id: str):
    try:
        save_scheduler_job_from_payload(job_id, dict(request.form), username=_username())
        flash("Pianificazione aggiornata. Il worker applichera' la modifica entro un minuto.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore salvataggio pianificazione %s: %s", job_id, exc)
        flash("Pianificazione non aggiornata. Dettaglio tecnico registrato nei log server.", "danger")
    return redirect(url_for("scheduler_admin.dashboard"))


@scheduler_admin.post("/admin/pianificazioni/crea")
@superadmin_required
def create_job():
    try:
        created = create_scheduler_job_from_payload(dict(request.form), username=_username())
        flash(f"Pianificazione creata: {created['name']}.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore creazione pianificazione: %s", exc)
        flash("Pianificazione non creata. Dettaglio tecnico registrato nei log server.", "danger")
    return redirect(url_for("scheduler_admin.dashboard"))


@scheduler_admin.post("/admin/pianificazioni/<string:job_id>/esegui")
@superadmin_required
def run_job(job_id: str):
    try:
        request_scheduler_run(job_id, username=_username())
        flash("Esecuzione richiesta. Il worker la prende in carico senza bloccare la console.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore richiesta esecuzione %s: %s", job_id, exc)
        flash("Esecuzione non richiesta. Dettaglio tecnico registrato nei log server.", "danger")
    return redirect(url_for("scheduler_admin.dashboard"))


@scheduler_admin.post("/admin/pianificazioni/fonti-legali/annulla")
@superadmin_required
def cancel_legal_sources():
    try:
        result = cancel_legal_source_runs(username=_username())
        cancelled = int(result.get("cancelled") or 0)
        if cancelled:
            flash(
                f"Controlli fonti legali annullati: {cancelled} esecuzioni aperte chiuse.",
                "success",
            )
        else:
            flash("Nessuna esecuzione fonti legali aperta da annullare.", "info")
    except Exception as exc:
        current_app.logger.exception("Errore annullamento controlli fonti legali: %s", exc)
        flash("Annullamento non completato. Dettaglio tecnico registrato nei log server.", "danger")
    return redirect(url_for("scheduler_admin.dashboard"))
