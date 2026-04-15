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

import os
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, g, jsonify,
    redirect, render_template, request, url_for,
)
from werkzeug.utils import secure_filename

from lex.providers.local_ai_service import get_local_ai_service
from lex.providers.ollama_runtime import (
    clear_ollama_runtime_resolution_cache,
    refresh_live_ollama_runtime,
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


def _firma_upload_dir() -> Path:
    cfg_path = Path(current_app.config.get("STUDIO_CONFIG", "./config/studio.json"))
    return cfg_path.parent / "firma_uploads"


def _local_signer_meta() -> dict[str, str]:
    tools_dir = Path(__file__).resolve().parents[2] / "tools"
    dist_dir  = tools_dir / "dist"
    source = (tools_dir / "local_signer.py").read_text(encoding="utf-8")
    import re as _re

    match = _re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', source)
    version = match.group(1) if match else "n.d."

    # Determina il filename Windows mostrato in UI.
    # L'eseguibile .exe resta il pacchetto ufficiale pubblicato per Windows.
    win_cmd  = dist_dir / f"SetupLocalSigner-{version}.cmd"
    win_exe  = dist_dir / f"SetupLocalSigner-{version}.exe"
    win_ps1  = dist_dir / f"SetupLocalSigner-{version}.ps1"
    if win_exe.exists():
        windows_filename = win_exe.name
        windows_tipo     = "exe"
    elif win_cmd.exists():
        windows_filename = win_exe.name
        windows_tipo     = "exe_pending"
    elif win_ps1.exists():
        windows_filename = win_exe.name
        windows_tipo     = "ps1_offline"
    else:
        windows_filename = f"SetupLocalSigner-{version}.exe"
        windows_tipo     = "exe_pending"

    return {
        "version": version,
        "download_page": "https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma",
        "windows_filename": windows_filename,
        "windows_tipo": windows_tipo,
        "windows_script_filename": f"InstallaLocalSigner-{version}.ps1",
        "macos_filename": f"InstallaLocalSigner-{version}.command",
        "linux_filename": f"InstallaLocalSigner-{version}.run",
        "python_filename": f"local_signer-{version}.py",
    }


def _salva_upload_firma(storage, prefix: str, allowed_exts: set[str]) -> str:
    if not storage or not getattr(storage, "filename", ""):
        return ""
    filename = secure_filename(storage.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in allowed_exts:
        allowed = ", ".join(sorted(allowed_exts))
        raise ValueError(
            f"Formato file non valido per {prefix.replace('_', ' ')}. "
            f"Estensioni ammesse: {allowed}."
        )
    dest_dir = _firma_upload_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{prefix}{suffix}"
    storage.save(dest)
    return dest.as_posix()


def _applica_ad_app(cfg):
    """Sincronizza la configurazione salvata con app.config (nessun restart)."""
    from pct.local_ai import strip_api_suffix

    app = current_app._get_current_object()
    s = cfg.studio
    # Dati studio
    app.config["STUDIO_NOME"]      = s.nome
    app.config["STUDIO_AVVOCATO"]  = s.avvocato
    app.config["STUDIO_PIVA"]      = s.piva
    app.config["STUDIO_CF"]        = s.cf
    app.config["STUDIO_INDIRIZZO"] = s.indirizzo
    app.config["STUDIO_IBAN"]      = s.iban
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
    # AI locale / compat legacy assistente Ollama
    app.config["LOCAL_AI_ENABLED"] = cfg.ai.enabled
    app.config["LOCAL_AI_BASE_URL"] = cfg.ai.base_url
    app.config["LOCAL_AI_AUTO_BOOTSTRAP"] = cfg.ai.auto_bootstrap
    app.config["LOCAL_AI_CHAT_MODEL"] = cfg.ai.chat_model
    app.config["LOCAL_AI_EMBED_MODEL"] = cfg.ai.embed_model
    app.config["LOCAL_AI_KEEP_ALIVE"] = cfg.ai.keep_alive
    app.config["LOCAL_AI_AUTO_INDEX_DOCUMENTS"] = cfg.ai.auto_index_documents
    app.config["OLLAMA_URL"] = strip_api_suffix(cfg.ai.base_url)
    app.config["OLLAMA_MODEL"] = cfg.ai.chat_model or app.config.get("OLLAMA_MODEL", "mistral")
    clear_ollama_runtime_resolution_cache()
    # Reschedule job se lo scheduler è attivo
    _reschedule_jobs(app, cfg)


def _applica_override_ai_runtime(cfg):
    ai_cfg = cfg.ai

    if "PCT_LOCAL_AI_ENABLED" in os.environ:
        ai_cfg.enabled = os.getenv("PCT_LOCAL_AI_ENABLED", "1").lower() not in {"0", "false", "no"}
    if "PCT_LOCAL_AI_BASE_URL" in os.environ:
        ai_cfg.base_url = os.getenv("PCT_LOCAL_AI_BASE_URL", ai_cfg.base_url).strip() or ai_cfg.base_url
    if "PCT_LOCAL_AI_AUTO_BOOTSTRAP" in os.environ:
        ai_cfg.auto_bootstrap = os.getenv("PCT_LOCAL_AI_AUTO_BOOTSTRAP", "1").lower() not in {"0", "false", "no"}
    if "PCT_LOCAL_AI_CHAT_MODEL" in os.environ:
        ai_cfg.chat_model = os.getenv("PCT_LOCAL_AI_CHAT_MODEL", "").strip()
    if "PCT_LOCAL_AI_EMBED_MODEL" in os.environ:
        ai_cfg.embed_model = os.getenv("PCT_LOCAL_AI_EMBED_MODEL", "").strip()
    if "PCT_LOCAL_AI_KEEP_ALIVE" in os.environ:
        ai_cfg.keep_alive = os.getenv("PCT_LOCAL_AI_KEEP_ALIVE", "10m").strip() or "10m"
    if "PCT_LOCAL_AI_AUTO_INDEX_DOCUMENTS" in os.environ:
        ai_cfg.auto_index_documents = os.getenv("PCT_LOCAL_AI_AUTO_INDEX_DOCUMENTS", "1").lower() not in {
            "0",
            "false",
            "no",
        }
    return cfg


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
            ConfigFirma, ConfigSMTP, ConfigWhatsApp, ConfigScheduler, ConfigLocalAI,
        )
        cfg = gs.config
        try:
            if tab == "studio":
                cfg.studio = ConfigDatiStudio(
                    nome=f.get("nome", "").strip(),
                    avvocato=f.get("avvocato", "").strip(),
                    piva=f.get("piva", "").strip(),
                    cf=f.get("cf", "").strip(),
                    indirizzo=f.get("indirizzo", "").strip(),
                    city=f.get("city", "").strip(),
                    province=f.get("province", "").strip().upper(),
                    patron_name=f.get("patron_name", "").strip(),
                    patron_day=int(f.get("patron_day", "0") or "0"),
                    patron_month=int(f.get("patron_month", "0") or "0"),
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
                backend_preferito = (f.get("firma_formato") or cfg.firma.backend_preferito or "auto").strip().lower()
                if backend_preferito not in {"auto", "pkcs11", "p12", "pem"}:
                    backend_preferito = "auto"
                p12_path = f.get("firma_p12_path", "").strip()
                cert_pem_path = f.get("firma_cert_pem_path", "").strip()
                key_pem_path = f.get("firma_key_pem_path", "").strip()
                p12_upload = request.files.get("firma_p12_file")
                cert_upload = request.files.get("firma_cert_pem_file")
                key_upload = request.files.get("firma_key_pem_file")
                if p12_upload and p12_upload.filename:
                    p12_path = _salva_upload_firma(p12_upload, "firma", {".p12", ".pfx"})
                if cert_upload and cert_upload.filename:
                    cert_pem_path = _salva_upload_firma(cert_upload, "firma_cert", {".crt", ".cer", ".pem"})
                if key_upload and key_upload.filename:
                    key_pem_path = _salva_upload_firma(key_upload, "firma_key", {".key", ".pem"})
                cfg.firma = ConfigFirma(
                    # P12
                    p12_path=p12_path,
                    password=pwd if pwd else cfg.firma.password,
                    # PEM
                    cert_pem_path=cert_pem_path,
                    key_pem_path=key_pem_path,
                    key_pem_password=key_pwd if key_pwd else cfg.firma.key_pem_password,
                    # PKCS#11 (token USB — Aruba Key)
                    pkcs11_library=f.get("pkcs11_library", "").strip(),
                    pkcs11_slot=f.get("pkcs11_slot", "").strip(),
                    pkcs11_label=f.get("pkcs11_label", "").strip(),
                    # Comune
                    cf_avvocato=f.get("firma_cf_avvocato", "").strip(),
                    backend_preferito=backend_preferito,
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
            elif tab == "ai":
                cfg.ai = ConfigLocalAI(
                    enabled=bool(f.get("ai_enabled")),
                    base_url=f.get("ai_base_url", "http://127.0.0.1:11434/api").strip(),
                    auto_bootstrap=bool(f.get("ai_auto_bootstrap")),
                    chat_model=f.get("ai_chat_model", "").strip(),
                    embed_model=f.get("ai_embed_model", "").strip(),
                    keep_alive=f.get("ai_keep_alive", "10m").strip(),
                    auto_index_documents=bool(f.get("ai_auto_index_documents")),
                )
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("impostazioni.index", tab=tab))

        gs.aggiorna(cfg)
        _applica_ad_app(cfg)
        flash("Impostazioni salvate.", "success")
        return redirect(url_for("impostazioni.index", tab=tab))

    cfg = _applica_override_ai_runtime(gs.config)
    tab_attivo = request.args.get("tab", "studio")
    return render_template(
        "impostazioni/index.html",
        cfg=cfg,
        tab_attivo=tab_attivo,
        local_signer=_local_signer_meta(),
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


@impostazioni.route("/api/local-ai/status")
@_richiedi_login
def api_local_ai_status():
    try:
        return jsonify(get_local_ai_service().health_snapshot())
    except Exception as e:
        current_app.logger.exception("Errore api_local_ai_status: %s", e)
        return jsonify({"errore": str(e), "runtime": {"status": "error"}, "models": [], "counts": {}}), 200


@impostazioni.route("/api/local-ai/bootstrap", methods=["POST"])
@_richiedi_login
def api_local_ai_bootstrap():
    try:
        data = request.get_json(silent=True) or {}
        service = get_local_ai_service()
        result = service.bootstrap_runtime(force=bool(data.get("force")))
        refresh_live_ollama_runtime()
        return jsonify({"result": result, "status_payload": service.health_snapshot()})
    except Exception as e:
        current_app.logger.exception("Errore api_local_ai_bootstrap: %s", e)
        return jsonify({"errore": str(e), "runtime": {"status": "error"}}), 200
