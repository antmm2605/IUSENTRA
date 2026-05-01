from __future__ import annotations

from datetime import date
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from legal_intelligence.engine import LegalIntelligenceDailyEngine
from pct.portale import GestionePortale
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_legal_intelligence,
    get_legal_update_pipeline,
    get_normative_tables,
    get_scadenziario,
)
from web.blueprints.react_shell import render_react_shell_response

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


def _daily_db_path() -> Path:
    configured = current_app.config.get("LEGAL_INTELLIGENCE_DAILY_DB")
    if configured:
        return Path(configured)
    data_root = current_app.config.get("DATA_ROOT") or "data"
    return Path(data_root) / "legal_intelligence" / "daily.sqlite"


def _daily_engine() -> LegalIntelligenceDailyEngine:
    return LegalIntelligenceDailyEngine(_daily_db_path())


def _richiede_vista_classica() -> bool:
    return request.args.get("_legacy") == "1"


def _daily_snapshot() -> dict:
    try:
        return _daily_engine().dashboard_snapshot()
    except Exception as exc:
        current_app.logger.exception("Errore snapshot motore giornaliero Legal Intelligence: %s", exc)
        return {"last_run": None, "sources": [], "updates": [], "counts": {}, "error": str(exc)}


@legal_intelligence.route("/", methods=["GET"])
@_richiedi_login
def index():
    if not _richiede_vista_classica():
        return render_react_shell_response("ricerca-legale")
    return render_template(
        "legal_intelligence/index.html",
        snapshot=_snapshot(),
        updates_snapshot=get_legal_update_pipeline().dashboard_snapshot(),
        daily_snapshot=_daily_snapshot(),
        oggi=date.today(),
    )


@legal_intelligence.route("/news", methods=["GET"])
@_richiedi_login
def news():
    if not _richiede_vista_classica():
        return render_react_shell_response("legal-intelligence/news")

    pipeline = get_legal_update_pipeline()
    return render_template(
        "legal_intelligence/news.html",
        news_items=pipeline.repository.list_news(
            matter_slug=request.args.get("materia", ""),
            news_type=request.args.get("tipo", ""),
            limit=80,
        ),
        matters=pipeline.repository.list_matters(),
        selected_matter=request.args.get("materia", ""),
        selected_type=request.args.get("tipo", ""),
        snapshot=pipeline.dashboard_snapshot(),
        oggi=date.today(),
    )


@legal_intelligence.route("/news/<string:slug>", methods=["GET"])
@_richiedi_login
def dettaglio_news(slug: str):
    pipeline = get_legal_update_pipeline()
    news_item = pipeline.repository.get_news_by_slug(slug)
    if not news_item:
        flash("News non trovata o non ancora pubblicata.", "warning")
        return redirect(url_for("legal_intelligence.news"))
    return render_template(
        "legal_intelligence/news_detail.html",
        news_item=news_item,
        oggi=date.today(),
    )


@legal_intelligence.route("/mediazione", methods=["GET"])
@_richiedi_login
def registro_mediazione():
    if not _richiede_vista_classica():
        return render_react_shell_response("legal-intelligence/mediazione")

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


@legal_intelligence.route("/daily/esegui", methods=["POST"])
@_richiedi_login
def esegui_daily_sync():
    try:
        report = _daily_engine().run_daily_sync()
        flash(
            "Controllo giornaliero completato: "
            f"{report.get('sources_checked', 0)} fonti controllate, "
            f"{report.get('updates_detected', 0)} variazioni rilevate, "
            f"{report.get('updates_applied', 0)} applicate, "
            f"{report.get('pending_review', 0)} in revisione.",
            "success" if not report.get("errors_count") else "warning",
        )
    except Exception as exc:
        current_app.logger.exception("Errore controllo giornaliero Legal Intelligence: %s", exc)
        flash(f"Controllo giornaliero non completato: {exc}", "danger")
    return redirect(url_for("legal_intelligence.index"))


@legal_intelligence.route("/daily/update/<int:update_id>/approva", methods=["POST"])
@_richiedi_login
def approva_daily_update(update_id: int):
    try:
        _daily_engine().approve_update(update_id)
        flash("Aggiornamento approvato e registrato nel motore Legal Intelligence.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore approvazione update Legal Intelligence %s: %s", update_id, exc)
        flash(f"Approvazione non riuscita: {exc}", "danger")
    return redirect(url_for("legal_intelligence.index"))


@legal_intelligence.route("/daily/update/<int:update_id>/diff", methods=["GET"])
@_richiedi_login
def diff_daily_update(update_id: int):
    update = _daily_engine().get_update(update_id)
    if not update:
        flash("Aggiornamento non trovato.", "warning")
        return redirect(url_for("legal_intelligence.index"))
    return render_template("legal_intelligence/daily_diff.html", update=update, oggi=date.today())


@legal_intelligence.route("/daily/rigenera-indice-ai", methods=["POST"])
@_richiedi_login
def rigenera_indice_ai_daily():
    flash(
        "Rigenerazione indice AI registrata. Gli aggiornamenti approvati verranno inclusi nella prossima reindicizzazione.",
        "info",
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


@legal_intelligence.route("/api/news", methods=["GET"])
@_richiedi_login
def api_news():
    try:
        pipeline = get_legal_update_pipeline()
        return jsonify(
            {
                "ok": True,
                "items": pipeline.repository.list_news(
                    matter_slug=request.args.get("materia", ""),
                    news_type=request.args.get("tipo", ""),
                    limit=int(request.args.get("limit") or 50),
                ),
            }
        )
    except Exception as exc:
        current_app.logger.exception("Errore legal_intelligence.api_news: %s", exc)
        return jsonify({"ok": False, "errore": str(exc)}), 200
