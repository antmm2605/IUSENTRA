from __future__ import annotations

from datetime import date
from functools import wraps

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from pct.portale import GestionePortale
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_legal_intelligence,
    get_normative_tables,
    get_scadenziario,
)

legal_intelligence = Blueprint("legal_intelligence", __name__, url_prefix="/legal-intelligence")


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def _carica_portali():
    try:
        gestore = GestionePortale(
            db_path=current_app.config.get("PORTALE_DB", "./portale/portali.json"),
            uploads_dir=current_app.config.get("PORTALE_UPLOADS", "./portale/uploads"),
        )
        return gestore.tutti(includi_inattivi=False)
    except Exception:
        return []


def _snapshot():
    return get_legal_intelligence().build_dashboard_snapshot(
        fascicoli=get_fascicoli().tutti(archiviati=True),
        clienti=get_clienti().tutti(),
        appuntamenti=get_agenda().tutti(),
        scadenze=get_scadenziario().tutte(),
        portali=_carica_portali(),
    )


@legal_intelligence.route("/", methods=["GET"])
@_richiedi_login
def index():
    return render_template(
        "legal_intelligence/index.html",
        snapshot=_snapshot(),
        oggi=date.today(),
    )


@legal_intelligence.route("/mediazione", methods=["GET"])
@_richiedi_login
def registro_mediazione():
    return render_template(
        "legal_intelligence/mediazione.html",
        snapshot=_snapshot(),
        registro=get_legal_intelligence().mediazione_registry_snapshot(
            q=request.args.get("q", ""),
            city=request.args.get("city", ""),
            registry_number=request.args.get("registry_number", ""),
            organismo_type=request.args.get("organismo_type", ""),
        ),
        oggi=date.today(),
    )


@legal_intelligence.route("/monitor/esegui", methods=["POST"])
@_richiedi_login
def esegui_monitor():
    report = get_legal_intelligence().run_monitor_cycle()
    if report.get("ok"):
        flash(
            f"Monitoraggio completato: {report.get('successful', 0)} fonti controllate correttamente.",
            "success",
        )
    else:
        flash(
            f"Monitoraggio completato con criticita: {report.get('failed', 0)} fonti da verificare.",
            "warning",
        )
    return redirect(url_for("legal_intelligence.index"))


@legal_intelligence.route("/sync/esegui", methods=["POST"])
@_richiedi_login
def esegui_sync_normativo():
    report = get_legal_intelligence().sync_normative_tables()
    if report.get("review_required"):
        flash(
            f"Sync completato: {report.get('updated', 0)} tabelle aggiornate, {report.get('review_required', 0)} da verificare.",
            "warning",
        )
    else:
        flash(
            f"Sync completato: {report.get('updated', 0)} tabelle aggiornate e archivio normativo riallineato.",
            "success",
        )
    return redirect(url_for("legal_intelligence.index"))


@legal_intelligence.route("/mediazione/sync", methods=["POST"])
@_richiedi_login
def esegui_sync_registro_mediazione():
    report = get_legal_intelligence().sync_normative_tables(source_ids=["registro_mediazione"])
    mediazione = dict(report.get("mediazione_registry") or {})
    if mediazione.get("ok") and not mediazione.get("used_cached_rows"):
        flash(
            f"Registro mediazione sincronizzato: {mediazione.get('rows', 0)} organismi disponibili nel gestionale.",
            "success",
        )
    elif mediazione.get("used_cached_rows"):
        flash(
            "Registro diretto ministeriale non raggiungibile. "
            f"Il gestionale continua a mostrare {mediazione.get('rows', 0)} organismi gia presenti in cache. "
            + str(mediazione.get("warning") or ""),
            "warning",
        )
    else:
        flash(
            "Registro mediazione non aggiornato automaticamente. "
            + str(mediazione.get("warning") or "Verificare la fonte ministeriale ufficiale."),
            "warning",
        )
    return redirect(url_for("legal_intelligence.registro_mediazione"))


@legal_intelligence.route("/mediazione/import", methods=["POST"])
@_richiedi_login
def importa_registro_mediazione():
    upload = request.files.get("snapshot_file")
    html_payload = request.form.get("html_content", "")
    filename = ""
    if upload and upload.filename:
        filename = upload.filename
        html_payload = upload.read()

    if not html_payload:
        flash(
            "Carica un file HTML del registro oppure incolla il sorgente HTML della pagina ufficiale.",
            "warning",
        )
        return redirect(url_for("legal_intelligence.registro_mediazione"))

    try:
        report = get_legal_intelligence().import_registro_mediazione_snapshot(
            html_payload,
            filename=filename,
        )
        flash(
            f"Snapshot ufficiale importato correttamente: {report.get('rows', 0)} organismi disponibili nel gestionale.",
            "success",
        )
    except Exception as exc:
        current_app.logger.exception("Errore import registro mediazione: %s", exc)
        flash(f"Importazione non riuscita: {exc}", "warning")
    return redirect(url_for("legal_intelligence.registro_mediazione"))


@legal_intelligence.route("/api/snapshot", methods=["GET"])
@_richiedi_login
def api_snapshot():
    try:
        return jsonify({"ok": True, "snapshot": _snapshot()})
    except Exception as exc:
        current_app.logger.exception("Errore legal_intelligence.api_snapshot: %s", exc)
        return jsonify({"ok": False, "errore": str(exc)}), 200


@legal_intelligence.route("/api/tabelle-normative", methods=["GET"])
@_richiedi_login
def api_tabelle_normative():
    try:
        return jsonify({"ok": True, "snapshot": get_normative_tables().snapshot()})
    except Exception as exc:
        current_app.logger.exception("Errore legal_intelligence.api_tabelle_normative: %s", exc)
        return jsonify({"ok": False, "errore": str(exc)}), 200
