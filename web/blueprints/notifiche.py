"""
web/blueprints/notifiche.py — Gestione notifiche WhatsApp.

URL base: /notifiche/
- Pannello per inviare messaggi WhatsApp manuali ai clienti
- Trigger promemoria appuntamenti domani
- Log ultime notifiche inviate
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime

from flask import (Blueprint, flash, g, jsonify, redirect,
                   render_template, request, url_for, current_app)

from web.helpers import get_clienti, get_agenda

notifiche = Blueprint("notifiche", __name__, url_prefix="/notifiche")


def _richiedi_login(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def _config_wa():
    from pct.notifiche_wa import ConfigWA
    cfg = current_app.config
    return ConfigWA(
        twilio_sid=cfg.get("TWILIO_SID", ""),
        twilio_token=cfg.get("TWILIO_TOKEN", ""),
        twilio_numero=cfg.get("TWILIO_NUMERO", ""),
        callmebot_key=cfg.get("CALLMEBOT_KEY", ""),
    )


def _log_path():
    return current_app.config.get("NOTIFICHE_LOG", "./notifiche/log.json")


def _scrivi_log(entry: dict):
    path = _log_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    log = []
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    log.insert(0, entry)
    log = log[:200]  # ultimi 200 eventi
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _leggi_log() -> list:
    path = _log_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


# ================================================================ PANNELLO

@notifiche.route("/", methods=["GET"])
@_richiedi_login
def pannello():
    config = _config_wa()
    clienti = get_clienti().tutti()
    clienti_by_id = {c.id: c for c in clienti}
    log = _leggi_log()
    from datetime import timedelta

    domani_dt = date.today() + timedelta(days=1)
    ag = get_agenda()
    app_domani = [a for a in ag.tutti() if a.data_ora_dt.date() == domani_dt]
    app_domani_con_cell = []
    for a in app_domani:
        if a.id_cliente:
            c = clienti_by_id.get(a.id_cliente)
            if c and getattr(getattr(c, "recapiti", None), "cellulare", ""):
                app_domani_con_cell.append(a)

    return render_template(
        "notifiche/pannello.html",
        config=config,
        clienti=clienti,
        clienti_by_id=clienti_by_id,
        log=log,
        app_domani=app_domani,
        app_domani_con_cell=app_domani_con_cell,
    )


# ================================================================ INVIA MESSAGGIO LIBERO

@notifiche.route("/invia", methods=["POST"])
@_richiedi_login
def invia():
    from pct.notifiche_wa import invia_messaggio, msg_libero
    f = request.form
    id_cliente = f.get("id_cliente", "").strip()
    testo = f.get("testo", "").strip()
    if not id_cliente or not testo:
        flash("Seleziona un cliente e scrivi il testo del messaggio prima di procedere.", "danger")
        return redirect(url_for("notifiche.pannello"))
    gc = get_clienti()
    cliente = gc.get(id_cliente)
    if not cliente:
        flash("Il cliente selezionato non e' disponibile. Aggiorna la pagina e riprova.", "danger")
        return redirect(url_for("notifiche.pannello"))
    numero = getattr(getattr(cliente, "recapiti", None), "cellulare", "") or ""
    if not numero:
        flash("Per questo cliente non risulta un numero WhatsApp utilizzabile. Aggiorna l'anagrafica e riprova.", "warning")
        return redirect(url_for("notifiche.pannello"))
    config = _config_wa()
    studio_nome = current_app.config.get("STUDIO_NOME", "Studio Legale PCT")
    messaggio = msg_libero(cliente.nome_completo, testo, studio_nome)
    esito = invia_messaggio(numero, messaggio, config)
    _scrivi_log({
        "ts": datetime.now().isoformat(),
        "tipo": "libero",
        "cliente": cliente.nome_completo,
        "numero": numero,
        "esito": esito,
        "utente": g.utente_corrente.username if g.utente_corrente else "",
    })
    if esito.get("ok") is True:
        flash(f"Messaggio inviato correttamente a {cliente.nome_completo}.", "success")
    elif esito.get("ok") is None:
        # wa.me link: apre pagina di conferma
        from flask import session
        session["wa_link_pending"] = {
            "link": esito["wa_link"],
            "cliente": cliente.nome_completo,
        }
        flash(
            "Canale automatico non configurato. Ho preparato un link WhatsApp per completare l'invio manualmente.",
            "info",
        )
    else:
        flash(f"Invio non completato: {esito.get('errore', 'errore sconosciuto')}", "danger")
    return redirect(url_for("notifiche.pannello"))


# ================================================================ PROMEMORIA DOMANI

@notifiche.route("/promemoria-domani", methods=["POST"])
@_richiedi_login
def promemoria_domani():
    from pct.notifiche_wa import promemoria_appuntamenti_di_domani
    config = _config_wa()
    studio_nome = current_app.config.get("STUDIO_NOME", "Studio Legale PCT")
    gc = get_clienti()
    ag = get_agenda()
    risultati = promemoria_appuntamenti_di_domani(
        agenda=ag,
        get_cliente_fn=gc.get,
        config=config,
        studio_nome=studio_nome,
    )
    for r in risultati:
        _scrivi_log({
            "ts": datetime.now().isoformat(),
            "tipo": "promemoria_appuntamento",
            "cliente": r["cliente"],
            "numero": r["numero"],
            "esito": r["esito"],
            "utente": g.utente_corrente.username if g.utente_corrente else "system",
        })
    if not risultati:
        flash("Per domani non risultano appuntamenti con un numero WhatsApp utilizzabile.", "info")
    else:
        ok = sum(1 for r in risultati if r["esito"].get("ok") is True)
        if ok == len(risultati):
            flash(
                f"Promemoria inviati correttamente: {ok} su {len(risultati)}.",
                "success",
            )
        elif ok > 0:
            flash(
                f"Promemoria elaborati: {ok} inviati automaticamente su {len(risultati)}. Controlla il registro per i restanti.",
                "warning",
            )
        else:
            flash(
                "Nessun promemoria e' stato inviato automaticamente. Verifica il canale configurato e i recapiti dei clienti.",
                "warning",
            )
    return redirect(url_for("notifiche.pannello"))


# ================================================================ GENERA LINK WA (AJAX)

@notifiche.route("/wa-link", methods=["POST"])
@_richiedi_login
def wa_link_ajax():
    from pct.notifiche_wa import wa_link, msg_libero
    data = request.get_json(silent=True) or {}
    numero = data.get("numero", "").strip()
    testo = data.get("testo", "").strip()
    if not numero or not testo:
        return jsonify({"errore": "Seleziona un cliente con numero WhatsApp e inserisci il testo del messaggio."}), 400
    link = wa_link(numero, testo)
    return jsonify({"link": link})
