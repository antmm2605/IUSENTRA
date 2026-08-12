"""
web/blueprints/impostazioni.py — Pannello impostazioni studio.

Routes:
  GET/POST  /impostazioni                → pagina principale (tabs)
  POST      /impostazioni/test/pec-smtp  → AJAX test SMTP PEC
  POST      /impostazioni/test/pec-imap  → AJAX test IMAP PEC
  POST      /impostazioni/test/smtp      → AJAX test SMTP email
  POST      /impostazioni/test/whatsapp  → AJAX test WhatsApp
"""
from __future__ import annotations

from functools import wraps

from flask import (
    Blueprint, current_app, flash, g, jsonify,
    redirect, render_template, request, url_for,
)

impostazioni = Blueprint("impostazioni", __name__)


# ─────────────────────────────────────────────────────────── helpers

def _richiedi_login(f):
    @wraps(f)
    def w(*a, **kw):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return w


def _get_gestore():
    from pct.config_studio import GestioneConfigStudio
    return GestioneConfigStudio(
        config_path=current_app.config.get("STUDIO_CONFIG", "./config/studio.json")
    )


def _applica_ad_app(cfg):
    """Sincronizza la configurazione salvata con app.config (nessun restart)."""
    from pct.studio_address import compose_studio_address

    app = current_app._get_current_object()
    s = cfg.studio
    # Dati studio
    app.config["STUDIO_NOME"]      = s.nome
    app.config["STUDIO_AVVOCATO"]  = s.avvocato
    app.config["STUDIO_PIVA"]      = s.piva
    app.config["STUDIO_CF"]        = s.cf
    app.config["STUDIO_INDIRIZZO_VIA"] = s.indirizzo
    app.config["STUDIO_CAP"]       = getattr(s, "cap", "")
    app.config["STUDIO_CITY"]      = s.city
    app.config["STUDIO_PROVINCE"]  = s.province
    app.config["STUDIO_INDIRIZZO"] = compose_studio_address(
        indirizzo=s.indirizzo,
        cap=getattr(s, "cap", ""),
        city=s.city,
        province=s.province,
    )
    app.config["STUDIO_IBAN"]      = s.iban
    app.config["STUDIO_BANCA"]     = s.banca
    app.config["STUDIO_BIC_SWIFT"] = getattr(s, "bic_swift", "")
    # SMTP
    app.config["SMTP_HOST"]      = cfg.smtp.host
    app.config["SMTP_PORT"]      = cfg.smtp.port
    app.config["SMTP_USER"]      = cfg.smtp.username
    app.config["SMTP_PASS"]      = cfg.smtp.password
    app.config["SMTP_FROM"]      = cfg.smtp.from_address
    app.config["SMTP_FROM_NAME"] = cfg.smtp.from_name or s.nome
    app.config["SMTP_USE_TLS"]   = cfg.smtp.use_tls
    # WhatsApp
    app.config["TWILIO_SID"]    = cfg.whatsapp.twilio_sid
    app.config["TWILIO_TOKEN"]  = cfg.whatsapp.twilio_token
    app.config["TWILIO_NUMERO"] = cfg.whatsapp.twilio_numero
    app.config["CALLMEBOT_KEY"] = cfg.whatsapp.callmebot_key
    # Scheduler
    app.config["BACKUP_ORA"]      = cfg.scheduler.backup_ora
    app.config["WA_REMINDER_ORA"] = cfg.scheduler.wa_reminder_ora
    # Reschedule job se lo scheduler è attivo
    _reschedule_jobs(app, cfg)


def _reschedule_jobs(app, cfg):
    """Aggiorna gli orari dei job schedulati senza riavviare l'app."""
    try:
        from apscheduler.triggers.cron import CronTrigger
        scheduler = app.config.get("PCT_SCHEDULER")
        if scheduler is None or not scheduler.running:
            return
        h, m = map(int, cfg.scheduler.backup_ora.split(":"))
        scheduler.reschedule_job(
            "backup_giornaliero", trigger=CronTrigger(hour=h, minute=m)
        )
        wh, wm = map(int, cfg.scheduler.wa_reminder_ora.split(":"))
        scheduler.reschedule_job(
            "wa_reminder", trigger=CronTrigger(hour=wh, minute=wm)
        )
    except Exception:
        pass  # Lo scheduler potrebbe non essere avviato in certi ambienti


# ─────────────────────────────────────────────────────────── pagina principale

@impostazioni.route("/impostazioni", methods=["GET", "POST"])
@_richiedi_login
def index():
    gs = _get_gestore()

    if request.method == "POST":
        f = request.form
        tab = f.get("_tab", "studio")

        from pct.config_studio import (
            ConfigDatiStudio, ConfigPEC,
            ConfigFirma, ConfigSMTP, ConfigWhatsApp, ConfigScheduler,
        )
        cfg = gs.config

        if tab == "studio":
            cfg.studio = ConfigDatiStudio(
                nome=f.get("nome", "").strip(),
                avvocato=f.get("avvocato", "").strip(),
                deposito_telematico_role=getattr(cfg.studio, "deposito_telematico_role", ""),
                piva=f.get("piva", "").strip(),
                cf=f.get("cf", "").strip(),
                indirizzo=f.get("indirizzo", "").strip(),
                telefono=f.get("telefono", "").strip(),
                email=f.get("email", "").strip(),
                sito_web=f.get("sito_web", "").strip(),
                iban=f.get("iban", "").strip(),
                banca=f.get("banca", "").strip(),
                codice_fiscale_avvocato=f.get("codice_fiscale_avvocato", "").strip(),
            )
        elif tab == "pec":
            pwd = f.get("pec_password", "").strip()
            cfg.pec = ConfigPEC(
                indirizzo=f.get("pec_indirizzo", "").strip(),
                username=f.get("pec_username", "").strip(),
                password=pwd if pwd else cfg.pec.password,
                smtp_host=f.get("pec_smtp_host", "smtp.pec.aruba.it").strip(),
                smtp_port=int(f.get("pec_smtp_port", 465)),
                imap_host=f.get("pec_imap_host", "imaps.pec.aruba.it").strip(),
                imap_port=int(f.get("pec_imap_port", 993)),
                use_ssl=bool(f.get("pec_use_ssl")),
            )
        elif tab == "firma":
            pwd = f.get("firma_password", "").strip()
            key_pwd = f.get("firma_key_pem_password", "").strip()
            cfg.firma = ConfigFirma(
                # P12
                p12_path=f.get("firma_p12_path", "").strip(),
                password=pwd if pwd else cfg.firma.password,
                # PEM
                cert_pem_path=f.get("firma_cert_pem_path", "").strip(),
                key_pem_path=f.get("firma_key_pem_path", "").strip(),
                key_pem_password=key_pwd if key_pwd else cfg.firma.key_pem_password,
                # Comune
                cf_avvocato=f.get("firma_cf_avvocato", "").strip(),
            )
        elif tab == "smtp":
            pwd = f.get("smtp_password", "").strip()
            cfg.smtp = ConfigSMTP(
                host=f.get("smtp_host", "").strip(),
                port=int(f.get("smtp_port", 587)),
                username=f.get("smtp_username", "").strip(),
                password=pwd if pwd else cfg.smtp.password,
                from_address=f.get("smtp_from_address", "").strip(),
                from_name=f.get("smtp_from_name", "").strip(),
                use_tls=bool(f.get("smtp_use_tls")),
            )
        elif tab == "whatsapp":
            tok = f.get("twilio_token", "").strip()
            cfg.whatsapp = ConfigWhatsApp(
                twilio_sid=f.get("twilio_sid", "").strip(),
                twilio_token=tok if tok else cfg.whatsapp.twilio_token,
                twilio_numero=f.get("twilio_numero", "").strip(),
                callmebot_key=f.get("callmebot_key", "").strip(),
            )
        elif tab == "scheduler":
            cfg.scheduler = ConfigScheduler(
                backup_ora=f.get("backup_ora", "02:00").strip(),
                wa_reminder_ora=f.get("wa_reminder_ora", "18:00").strip(),
                backup_abilitato=bool(f.get("backup_abilitato")),
                wa_reminder_abilitato=bool(f.get("wa_reminder_abilitato")),
            )

        gs.aggiorna(cfg)
        _applica_ad_app(cfg)
        flash("Impostazioni salvate.", "success")
        return redirect(url_for("impostazioni.index", tab=tab))

    cfg = gs.config
    tab_attivo = request.args.get("tab", "studio")
    return render_template(
        "impostazioni/index.html",
        cfg=cfg,
        tab_attivo=tab_attivo,
    )


# ─────────────────────────────────────────────────────────── test connessioni (AJAX)

@impostazioni.route("/impostazioni/test/pec-smtp", methods=["POST"])
@_richiedi_login
def test_pec_smtp():
    from pct.config_studio import ConfigPEC, test_pec_smtp as _test
    data = request.get_json(force=True) or {}
    gs = _get_gestore()
    cfg_pec = gs.config.pec
    pec = ConfigPEC(
        indirizzo=data.get("indirizzo") or cfg_pec.indirizzo,
        username=data.get("username") or getattr(cfg_pec, "username", ""),
        password=data.get("password") or cfg_pec.password,
        smtp_host=data.get("smtp_host") or cfg_pec.smtp_host,
        smtp_port=int(data.get("smtp_port") or cfg_pec.smtp_port),
        imap_host=cfg_pec.imap_host,
        imap_port=cfg_pec.imap_port,
        use_ssl=data.get("use_ssl", cfg_pec.use_ssl),
    )
    return jsonify(_test(pec))


@impostazioni.route("/impostazioni/test/pec-imap", methods=["POST"])
@_richiedi_login
def test_pec_imap():
    from pct.config_studio import ConfigPEC, test_pec_imap as _test
    data = request.get_json(force=True) or {}
    gs = _get_gestore()
    cfg_pec = gs.config.pec
    pec = ConfigPEC(
        indirizzo=data.get("indirizzo") or cfg_pec.indirizzo,
        username=data.get("username") or getattr(cfg_pec, "username", ""),
        password=data.get("password") or cfg_pec.password,
        smtp_host=cfg_pec.smtp_host,
        smtp_port=cfg_pec.smtp_port,
        imap_host=data.get("imap_host") or cfg_pec.imap_host,
        imap_port=int(data.get("imap_port") or cfg_pec.imap_port),
        use_ssl=data.get("use_ssl", cfg_pec.use_ssl),
    )
    return jsonify(_test(pec))


@impostazioni.route("/impostazioni/test/smtp", methods=["POST"])
@_richiedi_login
def test_smtp():
    from pct.config_studio import ConfigSMTP, test_smtp_email as _test
    data = request.get_json(force=True) or {}
    gs = _get_gestore()
    cfg_smtp = gs.config.smtp
    smtp = ConfigSMTP(
        host=data.get("host") or cfg_smtp.host,
        port=int(data.get("port") or cfg_smtp.port),
        username=data.get("username") or cfg_smtp.username,
        password=data.get("password") or cfg_smtp.password,
        from_address=cfg_smtp.from_address,
        from_name=cfg_smtp.from_name,
        use_tls=data.get("use_tls", cfg_smtp.use_tls),
    )
    return jsonify(_test(smtp))


@impostazioni.route("/impostazioni/test/whatsapp", methods=["POST"])
@_richiedi_login
def test_whatsapp():
    from pct.config_studio import ConfigWhatsApp, test_whatsapp as _test
    data = request.get_json(force=True) or {}
    gs = _get_gestore()
    cfg_wa = gs.config.whatsapp
    wa = ConfigWhatsApp(
        twilio_sid=data.get("twilio_sid") or cfg_wa.twilio_sid,
        twilio_token=data.get("twilio_token") or cfg_wa.twilio_token,
        twilio_numero=data.get("twilio_numero") or cfg_wa.twilio_numero,
        callmebot_key=data.get("callmebot_key") or cfg_wa.callmebot_key,
    )
    return jsonify(_test(wa))
