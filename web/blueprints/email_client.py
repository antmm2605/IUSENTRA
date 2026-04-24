"""
web/blueprints/email_client.py — Client email completo per IUSENTRA.

Routes:
  GET       /email/                    → casella (inbox / inviati / cestino)
  GET       /email/messaggio/<id>      → dettaglio email
  GET/POST  /email/scrivi              → componi nuova email
  POST      /email/<id>/cestino        → sposta nel cestino
  POST      /email/<id>/ripristina     → ripristina dal cestino
  POST      /email/<id>/elimina        → elimina definitivamente
  POST      /email/svuota-cestino      → svuota cestino
  POST      /email/sincronizza         → AJAX: sync IMAP
  POST      /email/auto-esiti          → AJAX: aggiorna esiti PCT da email PST
  GET/POST  /email/impostazioni        → configurazione account email/IMAP
  GET       /api/email/stats           → AJAX: statistiche casella
"""
from __future__ import annotations

import mimetypes
import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Blueprint, abort, current_app, flash, g, jsonify,
    redirect, render_template, request, send_file, url_for, Response,
)
from pct.config_studio import _SMTPv4, _SMTP_SSLv4

email_client = Blueprint("email_client", __name__, url_prefix="/email")


# ─────────────────────────────────────────────────────────── Helpers

def _login_required(f):
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def _get_gestore():
    """Ritorna GestioneEmailRicevute con path configurato."""
    from pct.email_client import GestioneEmailRicevute
    db_path = current_app.config.get(
        "EMAIL_CASELLA_DB",
        os.environ.get("PCT_EMAIL_DB", "./email/casella.json"),
    )
    return GestioneEmailRicevute(db_path=db_path)


def _get_config_email():
    """Ritorna ConfigSMTP (campo smtp) dallo studio config."""
    try:
        from pct.config_studio import GestioneConfigStudio
        cfg_path = current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
        cfg = GestioneConfigStudio(config_path=cfg_path).config
        return cfg.smtp if cfg and hasattr(cfg, "smtp") else None
    except Exception:
        return None


def _get_config_pec():
    """Ritorna ConfigPEC dallo studio config."""
    try:
        from pct.config_studio import GestioneConfigStudio
        cfg_path = current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
        cfg = GestioneConfigStudio(config_path=cfg_path).config
        return cfg.pec if cfg and hasattr(cfg, "pec") else None
    except Exception:
        return None


def _pec_state_path() -> str:
    fascicoli_db = current_app.config.get("FASCICOLI_DB", "./fascicoli/fascicoli.json")
    return os.path.join(
        os.path.dirname(os.path.abspath(fascicoli_db)),
        "pec_cancelleria_state.json",
    )


def _get_fascicoli():
    """Ritorna il repository fascicoli tenant-aware con tutti i path runtime."""
    from web.helpers import get_fascicoli

    return get_fascicoli()


def _audit(azione: str, dettagli: str = ""):
    try:
        from pct.auth import GestioneUtenti
        u = g.get("utente_corrente")
        if not u:
            return
        gu = GestioneUtenti(
            db_path=current_app.config.get("AUTH_DB", "./auth/utenti.json"),
            audit_path=current_app.config.get("AUDIT_DB", "./auth/audit.json"),
        )
        gu.registra_audit(u.id, azione, dettagli=dettagli)
    except Exception:
        pass


# ─────────────────────────────────────────────────────────── Route principali

@email_client.route("/")
@_login_required
def casella():
    """Vista principale della casella email."""
    ge = _get_gestore()
    cartella = request.args.get("cartella", "INBOX")
    q = request.args.get("q", "").strip()
    stato_lettura = request.args.get("stato", "").strip().upper()
    solo_non_lette = request.args.get("non_lette") == "1" or stato_lettura == "NON_LETTA"
    solo_pst = request.args.get("pst") == "1"
    con_allegati = request.args.get("con_allegati") == "1"
    stato_pct = request.args.get("stato_pct", "").strip().upper()
    origine = request.args.get("origine", "").strip().upper()
    data_da = request.args.get("data_da", "").strip()
    data_a = request.args.get("data_a", "").strip()

    from pct.email_client import CartellaEmail
    cartella_valida = cartella if cartella in (
        CartellaEmail.INBOX, CartellaEmail.INVIATI, CartellaEmail.CESTINO
    ) else CartellaEmail.INBOX

    # Sincronizza inviati da messaggi.py al volo
    _sync_inviati(ge)

    emails = ge.tutte(
        cartella=cartella_valida,
        solo_non_lette=solo_non_lette,
        q=q,
        stato_lettura=stato_lettura,
        solo_pst=solo_pst,
        con_allegati=con_allegati,
        stato_pct=stato_pct,
        origine=origine,
        data_da=data_da,
        data_a=data_a,
    )
    stats  = ge.statistiche()

    # Email selezionata per vista split (desktop)
    id_sel = request.args.get("id", "")
    email_sel = None
    if id_sel:
        email_sel = ge.get(id_sel)
        if email_sel and email_sel.stato == "NON_LETTA":
            ge.marca_letta(id_sel)
            email_sel.stato = "LETTA"
            stats = ge.statistiche()

    return render_template(
        "email/client.html",
        emails=emails,
        email_sel=email_sel,
        cartella=cartella_valida,
        q=q,
        solo_non_lette=solo_non_lette,
        stato_lettura=stato_lettura,
        solo_pst=solo_pst,
        con_allegati=con_allegati,
        stato_pct=stato_pct,
        origine=origine,
        data_da=data_da,
        data_a=data_a,
        has_advanced_filters=any([solo_pst, con_allegati, stato_pct, origine, data_da, data_a, stato_lettura]),
        stats=stats,
        oggi=date.today(),
    )


@email_client.route("/messaggio/<id_email>")
@_login_required
def dettaglio(id_email: str):
    """Vista dettaglio email (mobile o link diretto)."""
    ge = _get_gestore()
    em = ge.get(id_email)
    if not em:
        flash("Email non trovata.", "warning")
        return redirect(url_for("email_client.casella"))
    if em.stato == "NON_LETTA":
        ge.marca_letta(id_email)
        em.stato = "LETTA"
    return render_template("email/dettaglio.html", em=em, oggi=date.today())


@email_client.route("/messaggio/<id_email>/allegato/<int:indice_allegato>")
@_login_required
def allegato(id_email: str, indice_allegato: int):
    ge = _get_gestore()
    em = ge.get(id_email)
    if not em:
        abort(404)
    percorso = ge.percorso_allegato(em, indice_allegato)
    if not percorso:
        abort(404)
    info = (em.allegati or [])[indice_allegato]
    nome_download = info.get("nome") or info.get("nome_file") or percorso.name
    mime_salvato = str(info.get("mime") or "").strip()
    mime_da_nome = mimetypes.guess_type(nome_download)[0] or ""
    if mime_salvato in {"", "application/octet-stream", "binary/octet-stream"} and mime_da_nome:
        mimetype = mime_da_nome
    else:
        mimetype = mime_salvato or mime_da_nome or "application/octet-stream"
    if request.args.get("download") != "1" and mimetype == "message/rfc822":
        mimetype = "text/plain; charset=utf-8"
    return send_file(
        percorso,
        mimetype=mimetype,
        as_attachment=request.args.get("download") == "1",
        download_name=nome_download,
        conditional=True,
    )


def _redirect_email_next(default_cartella: str):
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("email_client.casella", cartella=default_cartella))


@email_client.route("/<id_email>/segna-letta", methods=["POST"])
@_login_required
def segna_letta(id_email: str):
    ge = _get_gestore()
    ge.marca_letta(id_email)
    return _redirect_email_next(request.form.get("cartella", "INBOX"))


@email_client.route("/<id_email>/segna-non-letta", methods=["POST"])
@_login_required
def segna_non_letta(id_email: str):
    ge = _get_gestore()
    ge.marca_non_letta(id_email)
    return _redirect_email_next(request.form.get("cartella", "INBOX"))


@email_client.route("/scrivi", methods=["GET", "POST"])
@_login_required
def scrivi():
    """Componi nuova email."""
    if request.method == "GET":
        # Pre-compila se passato in querystring (es. risposta)
        a = request.args.get("a", "")
        oggetto = request.args.get("oggetto", "")
        try:
            from pct.clienti import GestioneClienti
            gc = GestioneClienti(
                db_path=current_app.config.get("CLIENTI_DB", "./clienti/anagrafica.json")
            )
            clienti = gc.tutti()
        except Exception:
            clienti = []
        return render_template(
            "email/scrivi.html",
            a=a, oggetto=oggetto,
            clienti=clienti,
            oggi=date.today(),
        )

    # POST — invio
    f = request.form
    destinatario = f.get("a", "").strip()
    oggetto      = f.get("oggetto", "").strip()
    corpo_testo  = f.get("corpo", "").strip()
    id_cliente   = f.get("id_cliente", "").strip()

    if not destinatario or not oggetto:
        flash("Compilare almeno destinatario e oggetto.", "danger")
        return redirect(url_for("email_client.scrivi"))

    try:
        from pct.messaggi import GestioneMessaggi
        from pct.config_studio import GestioneConfigStudio
        cfg_path = current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
        cfg = GestioneConfigStudio(config_path=cfg_path).config
        db_path = current_app.config.get("MESSAGGI_DB", "./messaggi/storico.json")
        gm = GestioneMessaggi(
            config=None,
            db_path=db_path,
        )
        gm.invia_email(
            destinatario=destinatario,
            oggetto=oggetto,
            corpo_testo=corpo_testo,
            id_cliente=id_cliente,
        )
        # Aggiorna subito la casella inviati
        ge = _get_gestore()
        _sync_inviati(ge)
        flash("Email inviata con successo.", "success")
        _audit("email.inviata", f"A: {destinatario} | Ogg: {oggetto[:60]}")
        return redirect(url_for("email_client.casella", cartella="INVIATI"))
    except Exception as exc:
        flash(f"Errore invio: {exc}", "danger")
        return redirect(url_for("email_client.scrivi",
                                a=destinatario, oggetto=oggetto))


# ─────────────────────────────────────────────────────────── Azioni email

@email_client.route("/<id_email>/cestino", methods=["POST"])
@_login_required
def cestino(id_email: str):
    ge = _get_gestore()
    ge.sposta_cestino(id_email)
    cartella = request.form.get("cartella", "INBOX")
    return redirect(url_for("email_client.casella", cartella=cartella))


@email_client.route("/<id_email>/ripristina", methods=["POST"])
@_login_required
def ripristina(id_email: str):
    ge = _get_gestore()
    ge.ripristina(id_email)
    return redirect(url_for("email_client.casella", cartella="INBOX"))


@email_client.route("/<id_email>/elimina", methods=["POST"])
@_login_required
def elimina(id_email: str):
    ge = _get_gestore()
    ge.elimina_definitivamente(id_email)
    flash("Email eliminata definitivamente.", "success")
    return redirect(url_for("email_client.casella", cartella="CESTINO"))


@email_client.route("/svuota-cestino", methods=["POST"])
@_login_required
def svuota_cestino():
    ge = _get_gestore()
    n = ge.svuota_cestino()
    flash(f"Cestino svuotato ({n} email eliminate).", "success")
    return redirect(url_for("email_client.casella", cartella="CESTINO"))


# ─────────────────────────────────────────────────────────── Sync / IMAP

@email_client.route("/api/stats")
@_login_required
def stats_json():
    ge = _get_gestore()
    return jsonify(ge.statistiche())


@email_client.route("/sincronizza", methods=["POST"])
@_login_required
def sincronizza():
    """AJAX — sincronizza la casella IMAP e aggiorna gli esiti PCT."""
    ge = _get_gestore()

    # Determina config IMAP: preferisci PEC, fallback su email ordinaria
    pec_cfg   = _get_config_pec()
    email_cfg = _get_config_email()

    imap_host = imap_port = username = password = use_ssl = None

    if pec_cfg and getattr(pec_cfg, "imap_host", ""):
        imap_host = pec_cfg.imap_host
        imap_port = getattr(pec_cfg, "imap_port", 993)
        username  = pec_cfg.indirizzo
        password  = pec_cfg.password
        use_ssl   = getattr(pec_cfg, "use_ssl", True)
    elif email_cfg and getattr(email_cfg, "imap_host", ""):
        imap_host = email_cfg.imap_host
        imap_port = getattr(email_cfg, "imap_port", 993)
        username  = email_cfg.username
        password  = email_cfg.password
        use_ssl   = getattr(email_cfg, "use_ssl", True)

    if not imap_host or not username:
        return jsonify({
            "ok": False,
            "errore": "IMAP non configurato. Configura le credenziali in Impostazioni → Email.",
        })

    try:
        poll_report = {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}
        log_esiti = []
        auto_summary = {"aggiornati": 0, "non_abbinati": 0, "errori": 0, "totale": 0, "pst_in_attesa": 0}
        if pec_cfg and getattr(pec_cfg, "imap_host", ""):
            from pct.email_client import sincronizza_pec_e_fascicoli

            gf = _get_fascicoli()
            workflow = sincronizza_pec_e_fascicoli(
                gestione_email=ge,
                gestione_fascicoli=gf,
                config_pec=pec_cfg,
                state_path=_pec_state_path(),
                limite=100,
            )
            ris = workflow.get("sync", {})
            log_esiti = workflow.get("auto_esiti", []) or []
            auto_summary = _riassunto_auto_esiti_route(ge, log_esiti)
            poll_report = workflow.get("poll", {}) or poll_report
        else:
            ris = ge.sincronizza_imap(
                imap_host=imap_host,
                imap_port=int(imap_port or 993),
                username=username,
                password=password,
                use_ssl=bool(use_ssl),
                cartelle_imap=["INBOX"],
                limite=100,
                timeout_seconds=15,
            )
            if ris.get("pst_trovate", 0) > 0:
                log_esiti = _auto_esiti(ge)
                auto_summary = _riassunto_auto_esiti_route(ge, log_esiti)

        _sync_inviati(ge)

        _audit("email.sincronizzata", f"Nuove: {ris.get('nuove', 0)}, PST: {ris.get('pst_trovate', 0)}")
        sync_errore = str(ris.get("errore", "") or "").strip()
        warning = bool(sync_errore)
        messaggio = "Sincronizzazione completata."
        if warning:
            messaggio = "Sincronizzazione completata con avvisi. Sincronizzazione IMAP non completata."

        return jsonify({
            "ok": True,
            "warning": warning,
            "messaggio": messaggio,
            "nuove": ris.get("nuove", 0),
            "pst_trovate": ris.get("pst_trovate", 0),
            "allegati_salvati": ris.get("allegati_salvati", 0),
            "esiti_aggiornati": auto_summary["aggiornati"],
            "non_abbinati": auto_summary["non_abbinati"],
            "pst_in_attesa": auto_summary["pst_in_attesa"],
            "comunicazioni_cancelleria": poll_report.get("associati", 0),
            "report": poll_report,
            "errore": sync_errore,
            "sync_errore": sync_errore,
            "stats": ge.statistiche(),
        })
    except Exception as exc:
        return jsonify({"ok": False, "errore": str(exc)})


@email_client.route("/auto-esiti", methods=["POST"])
@_login_required
def auto_esiti():
    """AJAX — aggiorna esiti PCT da email PST già ricevute."""
    ge   = _get_gestore()
    log  = _auto_esiti(ge)
    auto_summary = _riassunto_auto_esiti_route(ge, log)
    comm_report = {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}
    try:
        from pct.email_client import aggiorna_comunicazioni_cancelleria_da_email

        gf = _get_fascicoli()
        comm_report = aggiorna_comunicazioni_cancelleria_da_email(ge, gf)
    except Exception as exc:
        log.append(f"Errore comunicazioni cancelleria: {exc}")
    warning = bool(comm_report.get("errori", 0) or auto_summary["errori"])
    if auto_summary["aggiornati"]:
        messaggio = f"{auto_summary['aggiornati']} esiti deposito aggiornati automaticamente."
    else:
        messaggio = "Nessun esito deposito nuovo da collegare ai fascicoli."
    if auto_summary["non_abbinati"]:
        messaggio += f" {auto_summary['non_abbinati']} PEC PST restano in attesa di abbinamento."
    if auto_summary["pst_in_attesa"] and not auto_summary["non_abbinati"]:
        messaggio += f" {auto_summary['pst_in_attesa']} PEC PST restano ancora da verificare."
    if comm_report.get("associati", 0):
        messaggio += f" Comunicazioni di cancelleria collegate: {comm_report.get('associati', 0)}."
    if warning:
        messaggio += " Alcune comunicazioni non sono state elaborate completamente."
    return jsonify({
        "ok": True,
        "warning": warning,
        "messaggio": messaggio,
        "aggiornati": auto_summary["aggiornati"],
        "esiti_aggiornati": auto_summary["aggiornati"],
        "non_abbinati": auto_summary["non_abbinati"],
        "pst_in_attesa": auto_summary["pst_in_attesa"],
        "comunicazioni_aggiornate": comm_report.get("associati", 0),
        "report": comm_report,
        "log": log,
    })


# ─────────────────────────────────────────────────────────── Impostazioni email

@email_client.route("/impostazioni", methods=["GET", "POST"])
@_login_required
def impostazioni():
    """Configurazione account email e IMAP."""
    from pct.config_studio import GestioneConfigStudio
    cfg_path = current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
    gs = GestioneConfigStudio(config_path=cfg_path)

    if request.method == "POST":
        f = request.form
        azione = f.get("azione", "salva")

        if azione == "test_smtp":
            return _test_smtp(gs)
        if azione == "test_imap":
            return _test_imap(gs, f)

        # Salva configurazione email (campo smtp in ConfigStudio)
        cfg = gs.config
        smtp = cfg.smtp  # ConfigSMTP

        smtp.host      = f.get("smtp_host", "").strip()
        smtp.port      = int(f.get("smtp_port") or 587)
        smtp.username  = f.get("username", "").strip()
        smtp.from_address = f.get("mittente_email", "").strip()
        smtp.from_name = f.get("mittente_nome", "").strip()
        smtp.use_tls   = f.get("use_tls") == "1"

        # IMAP — salvato nella configurazione PEC se non esiste campo dedicato
        # (usiamo il campo PEC imap per semplicità, oppure annotiamo come attr dinamico)
        imap_host = f.get("imap_host", "").strip()
        imap_port = int(f.get("imap_port") or 993)
        if imap_host and hasattr(cfg.pec, "imap_host"):
            cfg.pec.imap_host = imap_host
            cfg.pec.imap_port = imap_port

        pwd = f.get("password", "").strip()
        if pwd:
            smtp.password = pwd

        try:
            gs.salva(cfg)
            _audit("email.impostazioni_salvate")
            flash("Impostazioni email salvate.", "success")
        except Exception as exc:
            flash(f"Errore salvataggio: {exc}", "danger")

        return redirect(url_for("email_client.impostazioni"))

    cfg = gs.config
    email_cfg = getattr(cfg, "smtp", None)
    pec_cfg   = getattr(cfg, "pec", None)

    return render_template(
        "email/impostazioni.html",
        email_cfg=email_cfg,
        pec_cfg=pec_cfg,
        oggi=date.today(),
    )


# ─────────────────────────────────────────────────────────── API stats

@email_client.route("/impostazioni/reset-smtp", methods=["POST"])
@_login_required
def reset_smtp():
    """Azzera la configurazione SMTP e salva i valori di default."""
    from pct.config_studio import GestioneConfigStudio, ConfigSMTP
    cfg_path = current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
    gs = GestioneConfigStudio(config_path=cfg_path)
    cfg = gs.config

    # Recupera il nome dello studio per usarlo come from_name di default
    studio_nome = getattr(getattr(cfg, "studio", None), "nome", "Studio Legale")

    cfg.smtp = ConfigSMTP(
        host="",
        port=587,
        username="",
        password="",
        from_address="",
        from_name=studio_nome,
        use_tls=True,
    )

    try:
        gs.aggiorna(cfg)
        _audit("email.smtp_reset", "Configurazione SMTP azzerata dall'interfaccia web")
        return jsonify({"ok": True, "messaggio": "Configurazione SMTP azzerata. Inserisci le nuove credenziali e salva."})
    except Exception as exc:
        return jsonify({"ok": False, "errore": f"Errore durante il reset: {exc}"})




# ─────────────────────────────────────────────────────────── Privati

def _sync_inviati(ge) -> None:
    """Importa le email inviate da messaggi.py nella casella inviati."""
    try:
        from pct.messaggi import GestioneMessaggi, CanaleMsggio
        from pct.config_studio import GestioneConfigStudio
        cfg_path = current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
        cfg = GestioneConfigStudio(config_path=cfg_path).config
        db_path = current_app.config.get("MESSAGGI_DB", "./messaggi/storico.json")
        gm = GestioneMessaggi(config=None, db_path=db_path)
        inviati = [
            m for m in gm.tutti(canale=CanaleMsggio.EMAIL)
            if m.stato.value in ("INVIATO", "CONSEGNATO", "LETTO")
        ]
        ge.sincronizza_inviati(inviati)
    except Exception:
        pass


def _auto_esiti(ge) -> list:
    """Aggiorna gli EsitoDepositoPCT nei fascicoli dalle email PST."""
    try:
        from pct.email_client import aggiorna_esiti_da_email
        gf = _get_fascicoli()
        return aggiorna_esiti_da_email(ge, gf)
    except Exception as exc:
        return [f"Errore auto-esiti: {exc}"]


def _riassunto_auto_esiti_route(ge, log: list[str]) -> dict:
    from pct.email_client import riassunto_auto_esiti

    summary = riassunto_auto_esiti(log)
    summary["pst_in_attesa"] = sum(
        1 for em in ge._carica().values()
        if em.e_pst and not em.auto_registrata
    )
    return summary


def _test_smtp(gs) -> "Response":
    """Test connessione SMTP (AJAX)."""
    import smtplib, ssl as _ssl
    f = request.form
    host  = f.get("smtp_host", "").strip()
    port  = int(f.get("smtp_port") or 587)
    user  = f.get("username", "").strip()
    pwd   = f.get("password", "").strip()
    tls   = f.get("use_tls") == "1"
    if not host or not user or not pwd:
        return jsonify({"ok": False, "errore": "Compilare host, username e password."})
    try:
        ctx = _ssl.create_default_context()
        if port == 465:
            s = _SMTP_SSLv4(host, port, context=ctx, timeout=10)
        else:
            s = _SMTPv4(host, port, timeout=10)
            if tls:
                s.starttls(context=ctx)
        s.login(user, pwd)
        s.quit()
        return jsonify({"ok": True, "messaggio": f"Connessione SMTP a {host}:{port} OK."})
    except Exception as e:
        return jsonify({"ok": False, "errore": str(e)})


def _test_imap(gs, f) -> "Response":
    """Test connessione IMAP (AJAX)."""
    import imaplib as _imap
    host  = f.get("imap_host", "").strip()
    port  = int(f.get("imap_port") or 993)
    user  = f.get("username", "").strip()
    pwd   = f.get("password", "").strip()
    ssl_  = f.get("imap_ssl") == "1"
    if not host or not user or not pwd:
        return jsonify({"ok": False, "errore": "Compilare host IMAP, username e password."})
    try:
        if ssl_:
            m = _imap.IMAP4_SSL(host, port)
        else:
            m = _imap.IMAP4(host, port)
        m.login(user, pwd)
        m.logout()
        return jsonify({"ok": True, "messaggio": f"Connessione IMAP a {host}:{port} OK."})
    except Exception as e:
        return jsonify({"ok": False, "errore": str(e)})
