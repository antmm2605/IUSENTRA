from __future__ import annotations

from datetime import date, datetime
from functools import wraps

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for
from werkzeug.routing import BuildError

from pct.applicazioni_catalogo import (
    applicazioni_correlate,
    cerca_applicazioni,
    catalogo_applicazioni,
    get_applicazione,
    get_sezioni_catalogo,
    raggruppa_per_sezione,
    statistiche_catalogo,
)
from pct.portale import GestionePortale
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_legal_intelligence,
    get_scadenziario,
)

applicazioni = Blueprint("applicazioni", __name__, url_prefix="/applicazioni")


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


def _fmt_datetime_it(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d/%m/%Y %H:%M")
    except ValueError:
        pass
    for parser in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, parser).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    for parser in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, parser).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _resolve_entry_url(entry: dict) -> dict:
    payload = dict(entry)
    payload["detail_url"] = url_for("applicazioni.dettaglio", app_id=payload["id"])
    endpoint = payload.get("endpoint")
    params = dict(payload.get("params") or {})
    href = payload["detail_url"]
    if endpoint:
        try:
            href = url_for(endpoint, **params)
        except BuildError:
            href = payload["detail_url"]
    payload["href"] = href
    payload["is_direct"] = href != payload["detail_url"]
    return payload


def _resolve_grouped_entries(entries):
    grouped = []
    for section in raggruppa_per_sezione(entries):
        block = dict(section)
        block["items"] = [_resolve_entry_url(item) for item in section["items"]]
        grouped.append(block)
    return grouped


def _rassegna_rows(snapshot: dict) -> dict:
    source_rows = list(snapshot.get("source_rows") or [])
    stored_alerts = list(snapshot.get("stored_alerts") or [])
    consumer_hints = (
        "istat",
        "inflazione",
        "interess",
        "entrate",
        "fisc",
        "consum",
        "tfr",
        "locaz",
        "imu",
        "cedolare",
    )
    giuridiche = []
    for row in source_rows[:6]:
        giuridiche.append(
            {
                "title": row.get("nome") or "Fonte ufficiale",
                "subtitle": row.get("area") or "Monitoraggio",
                "summary": row.get("summary") or row.get("warning") or "Fonte monitorata dal gestionale.",
                "date_label": _fmt_datetime_it(row.get("last_check", "")) or "in aggiornamento",
                "url": row.get("official_url") or "",
            }
        )
    consumatori = []
    for row in source_rows:
        text = " ".join(
            [
                str(row.get("nome", "")),
                str(row.get("area", "")),
                str(row.get("summary", "")),
                str(row.get("warning", "")),
            ]
        ).lower()
        if not any(hint in text for hint in consumer_hints):
            continue
        consumatori.append(
            {
                "title": row.get("nome") or "Aggiornamento operativo",
                "subtitle": row.get("area") or "Monitoraggio",
                "summary": row.get("summary") or row.get("warning") or "Voce utile per clienti e consumatori.",
                "date_label": _fmt_datetime_it(row.get("last_check", "")) or "in aggiornamento",
                "url": row.get("official_url") or "",
            }
        )
        if len(consumatori) >= 6:
            break
    if not consumatori:
        for alert in stored_alerts[:6]:
            consumatori.append(
                {
                    "title": alert.get("title") or "Alert operativo",
                    "subtitle": f"Severita {alert.get('severity', 'media')}",
                    "summary": alert.get("details") or "Segnalazione disponibile nel monitoraggio interno.",
                    "date_label": "",
                    "url": alert.get("official_url") or "",
                }
            )
    return {"giuridiche": giuridiche, "consumatori": consumatori}


def _quick_links() -> list:
    return [
        {
            "title": "Strumenti Legali",
            "text": "Calcoli operativi, interessi, TFR, danni, successioni e moduli professionali.",
            "url": url_for("strumenti_legali.index"),
            "icon": "bi-grid-1x2",
            "accent": "primary",
        },
        {
            "title": "Ricerca Legale",
            "text": "Rassegna, fonti ufficiali, monitor normativi e registro mediazione.",
            "url": url_for("legal_intelligence.index"),
            "icon": "bi-diagram-3",
            "accent": "danger",
        },
        {
            "title": "Archivio Sentenze",
            "text": "Schede giurisprudenziali, massime, orientamenti e recupero assistito dalle fonti presidiate.",
            "url": url_for("giurisprudenza.index"),
            "icon": "bi-bank2",
            "accent": "info",
        },
        {
            "title": "Cabina Telematica",
            "text": "PST, PDP, PAT e PTT con workflow guidati, fascicoli interni e controlli.",
            "url": url_for("telematico_dashboard"),
            "icon": "bi-send-check",
            "accent": "dark",
        },
        {
            "title": "Template Atti",
            "text": "Modelli, procure, relazioni, note e schemi riusabili del gestionale.",
            "url": url_for("template_atti.catalogo"),
            "icon": "bi-file-earmark-richtext",
            "accent": "secondary",
        },
        {
            "title": "Fatturazione",
            "text": "Parcelle, fatture, compensi, documenti economici e avanzamento clienti.",
            "url": url_for("fatturazione.lista"),
            "icon": "bi-receipt",
            "accent": "success",
        },
        {
            "title": "Preventivi",
            "text": "Wizard guidati per preventivi civili e attivita stragiudiziali.",
            "url": url_for("preventivi.wizard"),
            "icon": "bi-calculator",
            "accent": "warning",
        },
    ]


@applicazioni.route("/", methods=["GET"])
@_richiedi_login
def index():
    q = (request.args.get("q") or "").strip()
    sezione = (request.args.get("sezione") or "").strip()
    stato = (request.args.get("stato") or "").strip()
    entries = cerca_applicazioni(q=q, sezione=sezione, stato=stato)
    snapshot = _snapshot()
    return render_template(
        "applicazioni/index.html",
        oggi=date.today(),
        query=q,
        sezione_sel=sezione,
        stato_sel=stato,
        sezioni=get_sezioni_catalogo(),
        grouped_entries=_resolve_grouped_entries(entries),
        stats=statistiche_catalogo(catalogo_applicazioni()),
        filtered_stats=statistiche_catalogo(entries),
        quick_links=_quick_links(),
        rassegna=_rassegna_rows(snapshot),
    )


@applicazioni.route("/<app_id>", methods=["GET"])
@_richiedi_login
def dettaglio(app_id: str):
    entry = get_applicazione(app_id)
    if not entry:
        flash("Applicazione non trovata nel catalogo.", "warning")
        return redirect(url_for("applicazioni.index"))
    resolved = _resolve_entry_url(entry)
    section = next((row for row in get_sezioni_catalogo() if row["id"] == resolved["section_id"]), None)
    correlati = [_resolve_entry_url(item) for item in applicazioni_correlate(app_id)]
    return render_template(
        "applicazioni/dettaglio.html",
        oggi=date.today(),
        entry=resolved,
        section=section,
        correlati=correlati,
    )
