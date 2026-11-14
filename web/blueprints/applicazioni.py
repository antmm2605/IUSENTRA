from __future__ import annotations

from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, g, redirect, request, url_for
from web.services.tenant_paths import tenant_data_path

from pct.applicazioni_catalogo import (
    get_applicazione,
)
from pct.portale import GestionePortale
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_legal_intelligence,
    get_scadenziario,
)
from web.blueprints.react_shell import render_react_shell_response

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
            db_path=tenant_data_path("PORTALE_DB", "./portale/portali.json"),
            uploads_dir=tenant_data_path("PORTALE_UPLOADS", "./portale/uploads"),
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


@applicazioni.route("/", methods=["GET", "POST"])
@_richiedi_login
def index():
    # Catalogo e funzioni delle applicazioni: pagina React (ApplicazionePage); esecuzioni da /api/v1/ui/applicazioni.
    if request.method == "POST":
        return redirect(request.path)
    return render_react_shell_response("applicazioni")


@applicazioni.route("/<app_id>", methods=["GET"])
@_richiedi_login
def dettaglio(app_id: str):
    entry = get_applicazione(app_id)
    if not entry:
        flash("Applicazione non trovata nel catalogo.", "warning")
        return redirect(url_for("applicazioni.index"))
    return redirect(url_for("applicazioni.index", app=app_id))
