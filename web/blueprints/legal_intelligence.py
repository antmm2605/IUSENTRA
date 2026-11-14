from __future__ import annotations

import io
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, flash, g, jsonify, redirect, request, send_file, url_for

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


def _percorso_react() -> str:
    """Percorso della pagina React: /legal-intelligence/* è l'alias storico di /ricerca-legale/*."""
    percorso = (request.path or "/").strip("/")
    if percorso.startswith("legal-intelligence"):
        percorso = "ricerca-legale" + percorso[len("legal-intelligence"):]
    return percorso


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
        return LegalIntelligenceDailyEngine.read_dashboard(_daily_db_path())
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
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())


@legal_intelligence.route("/news", methods=["GET"])
@_richiedi_login
def news():
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())


@legal_intelligence.route("/news/<string:slug>", methods=["GET"])
@_richiedi_login
def dettaglio_news(slug: str):
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())


@legal_intelligence.route("/mediazione", methods=["GET"])
@_richiedi_login
def registro_mediazione():
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())


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
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())


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
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())


@legal_intelligence.route("/fonte/<string:source_id>/scarica", methods=["GET"])
@_richiedi_login
def scarica_fonte(source_id: str):
    # Search results carry native document identities, not daily-monitor source
    # codes. Resolve their owners before asking for a daily homepage snapshot.
    if source_id.startswith(("normattiva:", "sentenzeweb:")):
        from flask import Response
        import hashlib
        from lex.retrieval.normativa_catalog import NormativaIndexUnavailable, leggi_chunk_archiviato
        try:
            if source_id.startswith("normattiva:"):
                row = leggi_chunk_archiviato(source_id)
                text = str((row or {}).get("normative_full_text") or "")
                title = str((row or {}).get("titolo") or "Fonte normativa")
                official_url = str((row or {}).get("url_origine") or "")
            else:
                from pct.sentenzeweb_corpus import configured_corpus
                corpus = configured_corpus(current_app.config)
                row = corpus.get_sentenza(int(source_id.split(":", 1)[1])) if corpus else None
                text = str((row or {}).get("testo_integrale") or "")
                title = str((row or {}).get("titolo") or "Provvedimento")
                official_url = str((row or {}).get("url_pagina_ufficiale") or "")
        except (NormativaIndexUnavailable, ValueError, OSError, sqlite3.Error):
            return Response("Fonte archiviata non riscontrata: nessun file esportato.", status=409, content_type="text/plain; charset=utf-8")
        if not row or not text:
            return Response("Testo archiviato non disponibile.", status=404, content_type="text/plain; charset=utf-8")
        digest = hashlib.sha256(text.encode()).hexdigest()
        body = f"Titolo: {title}\nIdentità archivio: {source_id}\nFonte: {official_url}\nSHA-256 del testo archiviato: {digest}\n\n" + text
        response = send_file(io.BytesIO(body.encode("utf-8")), mimetype="text/plain; charset=utf-8", as_attachment=True, download_name="testo_archiviato.txt", max_age=0)
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
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
    # Ricerca legale: pagine React (LegalIntelligencePage, RicercaLegaleSchedaPage).
    return render_react_shell_response(_percorso_react())
