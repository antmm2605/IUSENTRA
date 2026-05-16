from __future__ import annotations

import io
from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, send_file, url_for

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

legal_intelligence = Blueprint("legal_intelligence", __name__, url_prefix="/legal-intelligence")


def _cfg_path(key: str, default: str = "") -> str:
    paths = getattr(g, "data_paths", {}) or {}
    if key in paths:
        return str(paths[key] or default)
    if getattr(g, "tenant_context_missing", False):
        raise RuntimeError(
            "Contesto studio non disponibile per la richiesta corrente. "
            "Accesso ai dati bloccato per evitare letture cross-studio."
        )
    return str(current_app.config.get(key, default) or default)


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
            db_path=_cfg_path("PORTALE_DB", "./portale/portali.json"),
            uploads_dir=_cfg_path("PORTALE_UPLOADS", "./portale/uploads"),
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
    configured = _cfg_path("LEGAL_INTELLIGENCE_DAILY_DB")
    if configured:
        return Path(configured)
    intelligence_db = _cfg_path("LEGAL_INTELLIGENCE_DB")
    if intelligence_db:
        return Path(intelligence_db).resolve().parent / "daily.sqlite"
    data_root = str(current_app.config.get("DATA_ROOT") or "data")
    return Path(data_root) / "legal_intelligence" / "daily.sqlite"


def _daily_engine() -> LegalIntelligenceDailyEngine:
    return LegalIntelligenceDailyEngine(_daily_db_path())


def _daily_snapshot() -> dict:
    try:
        return _daily_engine().dashboard_snapshot()
    except Exception as exc:
        current_app.logger.exception("Errore snapshot motore giornaliero Legal Intelligence: %s", exc)
        return {"last_run": None, "sources": [], "updates": [], "counts": {}, "error": str(exc)}


def _ultime_news(limit: int = 6):
    try:
        return get_legal_update_pipeline().repository.list_news(limit=limit)
    except Exception:
        current_app.logger.exception("Errore lettura news per dashboard Legal Intelligence")
        return []


@legal_intelligence.route("/", methods=["GET"])
@_richiedi_login
def index():
    snapshot = _snapshot()
    daily = _daily_snapshot()
    return render_template(
        "legal_intelligence/index.html",
        snapshot=snapshot,
        updates_snapshot=get_legal_update_pipeline().dashboard_snapshot(),
        daily_snapshot=daily,
        ultime_news=_ultime_news(limit=6),
        active_tab=request.args.get("tab", "panoramica"),
        oggi=date.today(),
    )


@legal_intelligence.route("/news", methods=["GET"])
@_richiedi_login
def news():
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
        return redirect(url_for(".news"))
    return render_template(
        "legal_intelligence/news_detail.html",
        news_item=news_item,
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
            status=request.args.get("status", ""),
            tax_code=request.args.get("tax_code", ""),
            vat_number=request.args.get("vat_number", ""),
            has_email=request.args.get("has_email", ""),
            has_website=request.args.get("has_website", ""),
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
    return redirect(url_for(".index"))


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
    return redirect(url_for(".index"))


@legal_intelligence.route("/daily/update/<int:update_id>/approva", methods=["POST"])
@_richiedi_login
def approva_daily_update(update_id: int):
    try:
        _daily_engine().approve_update(update_id)
        flash("Aggiornamento approvato e registrato nel motore Legal Intelligence.", "success")
    except Exception as exc:
        current_app.logger.exception("Errore approvazione update Legal Intelligence %s: %s", update_id, exc)
        flash(f"Approvazione non riuscita: {exc}", "danger")
    return redirect(url_for(".index"))


@legal_intelligence.route("/daily/update/<int:update_id>/diff", methods=["GET"])
@_richiedi_login
def diff_daily_update(update_id: int):
    update = _daily_engine().get_update(update_id)
    if not update:
        flash("Aggiornamento non trovato.", "warning")
        return redirect(url_for(".index"))
    return render_template("legal_intelligence/daily_diff.html", update=update, oggi=date.today())


@legal_intelligence.route("/daily/rigenera-indice-ai", methods=["POST"])
@_richiedi_login
def rigenera_indice_ai_daily():
    flash(
        "Rigenerazione indice AI registrata. Gli aggiornamenti approvati verranno inclusi nella prossima reindicizzazione.",
        "info",
    )
    return redirect(url_for(".index"))


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
    return redirect(url_for(".index"))


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
    return redirect(url_for(".registro_mediazione"))


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
        return redirect(url_for(".registro_mediazione"))

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
    return redirect(url_for(".registro_mediazione"))


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


@legal_intelligence.route("/fonte/<string:source_id>", methods=["GET"])
@_richiedi_login
def scheda_fonte(source_id: str):
    snapshot = _snapshot()
    fonte_row = next((row for row in snapshot.get("source_rows", []) if row.get("id") == source_id), None)
    if not fonte_row:
        flash("Fonte non trovata nel registro Legal Intelligence.", "warning")
        return redirect(url_for(".index", tab="fonti"))
    snapshot_card = None
    try:
        snapshot_card = _daily_engine().get_source_card(source_id)
    except Exception:
        current_app.logger.exception("Errore caricamento scheda fonte %s", source_id)
    return render_template(
        "legal_intelligence/fonte_dettaglio.html",
        fonte=fonte_row,
        card=snapshot_card or {},
        oggi=date.today(),
    )


@legal_intelligence.route("/fonte/<string:source_id>/scarica", methods=["GET"])
@_richiedi_login
def scarica_fonte(source_id: str):
    try:
        latest = _daily_engine().latest_snapshot(source_id)
    except Exception as exc:
        current_app.logger.exception("Errore download fonte %s: %s", source_id, exc)
        flash(f"Impossibile recuperare lo snapshot archiviato: {exc}", "warning")
        return redirect(url_for(".scheda_fonte", source_id=source_id))
    if not latest or not latest.get("normalized_text"):
        flash(
            "Non e ancora disponibile uno snapshot archiviato per questa fonte. "
            "Esegui prima un controllo giornaliero dalla sezione Fonti.",
            "info",
        )
        return redirect(url_for(".scheda_fonte", source_id=source_id))
    fetched = latest.get("fetched_at") or datetime.utcnow().isoformat()
    safe_id = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in source_id)
    safe_when = fetched.replace(":", "").replace("T", "_").split(".")[0]
    filename = f"fonte_{safe_id}_{safe_when}.txt"
    header_lines = [
        f"Fonte: {source_id}",
        f"URL: {latest.get('url') or ''}",
        f"Hash SHA-256: {latest.get('content_sha256') or ''}",
        f"Scaricata il: {fetched}",
        f"ETag: {latest.get('etag') or '-'}",
        f"Last-Modified: {latest.get('last_modified') or '-'}",
        "-" * 80,
        "",
    ]
    body = "\n".join(header_lines) + (latest.get("normalized_text") or "")
    buffer = io.BytesIO(body.encode("utf-8"))
    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="text/plain; charset=utf-8",
        as_attachment=True,
        download_name=filename,
    )


@legal_intelligence.route("/ricerca", methods=["GET"])
@_richiedi_login
def ricerca_unificata():
    from web.services.legal_intelligence_research import build_unified_search

    query = (request.args.get("q") or "").strip()
    snapshot = _snapshot()
    pipeline = get_legal_update_pipeline()
    news_items = pipeline.repository.list_news(limit=120) if query else []
    mediazione_rows = snapshot.get("mediazione_registry", {}).get("rows", []) if query else []
    daily_updates = _daily_snapshot().get("updates", []) if query else []
    risultati = build_unified_search(
        query=query,
        snapshot=snapshot,
        news_items=news_items,
        mediazione_rows=mediazione_rows,
        daily_updates=daily_updates,
    )
    if request.args.get("formato") == "json":
        return jsonify({"ok": True, "risultati": risultati})
    return render_template(
        "legal_intelligence/ricerca.html",
        risultati=risultati,
        snapshot=snapshot,
        oggi=date.today(),
    )
