"""Casella email ordinaria per IUSENTRA.

La PEC resta sul repository ``EMAIL_CASELLA_DB``. Questa blueprint gestisce
solo posta ordinaria su ``EMAIL_ORDINARIA_DB`` e usa i parametri del tab
``Impostazioni -> Email SMTP`` per ricezione IMAP e invio SMTP.
"""

from __future__ import annotations

import mimetypes
import os
from datetime import date
from functools import wraps
from pathlib import Path
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    Response,
    send_file,
    url_for,
)

from pct.notifiche_legali import is_legal_notification_subject as _is_legal_notification_subject
from web.blueprints.react_shell import render_react_shell_response
from web.services.mailbox_sync_runtime import run_ordinary_mailbox_sync
from web.services.tenant_paths import TenantDataPathError, tenant_data_path
from werkzeug.utils import secure_filename

email_ordinaria = Blueprint("email_ordinaria", __name__, url_prefix="/email-ordinaria")


def _login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


def _legacy_requested() -> bool:
    return request.args.get("_legacy") == "1"


def _wants_json_response() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )


def _cfg_path(key: str, default: str = "", *aliases: str) -> str:
    return tenant_data_path(key, default, *aliases, require_tenant=True)


def _studio_config_path() -> str:
    return _cfg_path("STUDIO_CONFIG", "./config/studio.json", "CONFIG_STUDIO_DB")


def _save_compose_attachments() -> list[str]:
    uploads = [upload for upload in request.files.getlist("allegati") if upload and upload.filename]
    if not uploads:
        return []
    base = Path(_cfg_path("MESSAGGI_DB", "./messaggi/storico.json")).parent / "allegati_invio" / uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for index, upload in enumerate(uploads, start=1):
        filename = secure_filename(upload.filename or "") or f"allegato-{index}"
        target = base / filename
        stem = target.stem
        suffix = target.suffix
        counter = 2
        while target.exists():
            target = base / f"{stem}-{counter}{suffix}"
            counter += 1
        upload.save(target)
        saved.append(str(target))
    return saved


def _get_gestore():
    from pct.email_client import GestioneEmailRicevute

    return GestioneEmailRicevute(
        db_path=_cfg_path(
            "EMAIL_ORDINARIA_DB",
            os.environ.get("PCT_EMAIL_ORDINARIA_DB", "./email/ordinaria.json"),
        )
    )


def _get_config_smtp():
    try:
        from pct.config_studio import GestioneConfigStudio

        cfg = GestioneConfigStudio(config_path=_studio_config_path()).config
        return cfg.smtp if cfg and hasattr(cfg, "smtp") else None
    except Exception:
        return None


def _messaggi_config_da_smtp():
    from pct.messaggi import ConfigEmail, ConfigMessaggistica

    smtp = _get_config_smtp()
    studio_nome = "Studio Legale"
    try:
        from pct.config_studio import GestioneConfigStudio

        cfg = GestioneConfigStudio(config_path=_studio_config_path()).config
        studio_nome = getattr(getattr(cfg, "studio", None), "nome", "") or studio_nome
    except Exception:
        pass
    return ConfigMessaggistica(
        email=ConfigEmail(
            smtp_host=getattr(smtp, "host", "") if smtp else "",
            smtp_port=int(getattr(smtp, "port", 587) or 587) if smtp else 587,
            username=getattr(smtp, "username", "") if smtp else "",
            password=getattr(smtp, "password", "") if smtp else "",
            use_tls=bool(getattr(smtp, "use_tls", True)) if smtp else True,
            mittente_email=getattr(smtp, "from_address", "") if smtp else "",
            mittente_nome=getattr(smtp, "from_name", "") or studio_nome if smtp else studio_nome,
        ),
        studio_nome=studio_nome,
    )


def _audit(azione: str, dettagli: str = "") -> None:
    try:
        from pct.auth import GestioneUtenti

        utente = g.get("utente_corrente")
        if not utente:
            return
        GestioneUtenti(
            db_path=_cfg_path("AUTH_DB", "./auth/utenti.json"),
            audit_path=_cfg_path("AUDIT_DB", "./auth/audit.json"),
            secret_key=current_app.secret_key,
        ).registra_audit(utente.id, azione, dettagli=dettagli)
    except Exception:
        return


def _sync_inviati(gestore) -> None:
    """Allinea la cartella inviati ordinaria con lo storico messaggi EMAIL."""
    try:
        from pct.messaggi import CanaleMsggio, GestioneMessaggi

        db_path = _cfg_path("MESSAGGI_DB", "./messaggi/storico.json")
        manager = GestioneMessaggi(config=None, db_path=db_path)
        inviati = [
            msg
            for msg in manager.tutti(canale=CanaleMsggio.EMAIL)
            if getattr(getattr(msg, "stato", ""), "value", getattr(msg, "stato", ""))
            in {"INVIATO", "CONSEGNATO", "LETTO"}
        ]
        if inviati:
            gestore.sincronizza_inviati(inviati)
    except Exception:
        return


def _json_or_redirect(default_cartella: str):
    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in (request.headers.get("Accept") or ""):
        return jsonify({"ok": True, "messaggio": "Operazione eseguita.", "cartella": default_cartella})
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("email_ordinaria.casella", cartella=default_cartella))


@email_ordinaria.route("/")
@_login_required
def casella():
    if not _legacy_requested():
        return render_react_shell_response("email-ordinaria")
    return redirect(url_for("email_client.casella", _legacy=1))


@email_ordinaria.route("/scrivi", methods=["GET", "POST"])
@_login_required
def scrivi():
    """Composizione email ordinaria separata dalla casella PEC."""
    if request.method == "GET":
        try:
            from pct.clienti import GestioneClienti

            clienti = GestioneClienti(
                db_path=_cfg_path("CLIENTI_DB", "./clienti/anagrafica.json")
            ).tutti()
        except Exception:
            clienti = []
        return render_template(
            "email/scrivi.html",
            a=request.args.get("a", ""),
            oggetto=request.args.get("oggetto", ""),
            clienti=clienti,
            oggi=date.today(),
            compose_title="Componi email ordinaria",
            compose_subtitle="Il messaggio verra' inviato tramite la configurazione SMTP ordinaria dello studio.",
            compose_channel_label="Email ordinaria - SMTP",
            compose_form_action=url_for("email_ordinaria.scrivi"),
            compose_back_url=url_for("email_ordinaria.casella", cartella="INBOX"),
            compose_settings_url="/impostazioni?tab=smtp",
        )

    form = request.form
    destinatario = form.get("a", "").strip()
    oggetto = form.get("oggetto", "").strip()
    corpo_testo = form.get("corpo", "").strip()
    id_cliente = form.get("id_cliente", "").strip()

    if not destinatario or not oggetto:
        if _wants_json_response():
            return jsonify({"ok": False, "message": "Compila destinatario e oggetto."}), 400
        flash("Compilare almeno destinatario e oggetto.", "danger")
        return redirect(url_for("email_ordinaria.scrivi", a=destinatario, oggetto=oggetto))
    if _is_legal_notification_subject(oggetto):
        message = (
            "Questo e' un oggetto riservato alla notifica ex L. 53/1994. "
            "Per il cliente usa Comunicazione al cliente, senza relata e senza oggetto di notifica."
        )
        if _wants_json_response():
            return jsonify({"ok": False, "message": message, "redirect": "/notifiche-legali"}), 400
        flash(message, "warning")
        return redirect("/notifiche-legali")

    try:
        from pct.messaggi import StatoMessaggio, GestioneMessaggi

        messaggi = GestioneMessaggi(
            config=_messaggi_config_da_smtp(),
            db_path=_cfg_path("MESSAGGI_DB", "./messaggi/storico.json"),
        )
        allegati = _save_compose_attachments()
        msg = messaggi.invia_email(
            destinatario=destinatario,
            oggetto=oggetto,
            corpo_testo=corpo_testo,
            id_cliente=id_cliente,
            allegati=allegati,
        )
        if getattr(msg, "stato", None) == StatoMessaggio.FALLITO:
            raise RuntimeError(getattr(msg, "errore", "") or "invio non completato")
        gestore = _get_gestore()
        _sync_inviati(gestore)
        flash("Email ordinaria inviata con successo.", "success")
        _audit("email_ordinaria.inviata", f"A: {destinatario} | Ogg: {oggetto[:60]}")
        if _wants_json_response():
            return jsonify({"ok": True, "message": "Email ordinaria inviata con successo.", "redirect": url_for("email_ordinaria.casella", cartella="INVIATI")})
        return redirect(url_for("email_ordinaria.casella", cartella="INVIATI"))
    except Exception as exc:
        if _wants_json_response():
            return jsonify({"ok": False, "message": f"Invio email ordinaria non riuscito: {exc}"}), 400
        flash(f"Errore invio email ordinaria: {exc}", "danger")
        return redirect(url_for("email_ordinaria.scrivi", a=destinatario, oggetto=oggetto))


@email_ordinaria.route("/messaggio/<id_email>")
@_login_required
def dettaglio(id_email: str):
    if not _legacy_requested():
        return render_react_shell_response(f"email-ordinaria/messaggio/{id_email}")
    gestore = _get_gestore()
    em = gestore.get(id_email)
    if not em:
        flash("Email ordinaria non trovata.", "warning")
        return redirect(url_for("email_ordinaria.casella"))
    if em.stato == "NON_LETTA":
        gestore.marca_letta(id_email)
        em.stato = "LETTA"
    return render_template(
        "email/dettaglio.html",
        em=em,
        oggi=date.today(),
        email_route_prefix="email_ordinaria",
        email_back_endpoint="email_ordinaria.casella",
    )


@email_ordinaria.route("/messaggio/<id_email>/allegato/<int:indice_allegato>")
@_login_required
def allegato(id_email: str, indice_allegato: int):
    gestore = _get_gestore()
    email_obj = gestore.get(id_email)
    if not email_obj:
        abort(404)
    percorso = gestore.percorso_allegato(email_obj, indice_allegato)
    if not percorso:
        allegati = list(email_obj.allegati or [])
        if 0 <= indice_allegato < len(allegati):
            info = allegati[indice_allegato] or {}
            nome = info.get("nome") or info.get("nome_file") or "allegato"
            return Response(
                (
                    f"L'allegato {nome} non e' disponibile nello storico locale. "
                    "Esegui Sincronizza email; se resta assente, verifica che il messaggio "
                    "sia ancora presente nella casella."
                ),
                status=409,
                mimetype="text/plain; charset=utf-8",
            )
        abort(404)
    info = (email_obj.allegati or [])[indice_allegato]
    nome_download = info.get("nome") or info.get("nome_file") or Path(percorso).name
    mime_salvato = str(info.get("mime") or "").strip()
    mime_da_nome = mimetypes.guess_type(nome_download)[0] or ""
    mimetype = (
        mime_da_nome
        if mime_salvato in {"", "application/octet-stream", "binary/octet-stream"} and mime_da_nome
        else mime_salvato or mime_da_nome or "application/octet-stream"
    )
    return send_file(
        percorso,
        mimetype=mimetype,
        as_attachment=request.args.get("download") == "1",
        download_name=nome_download,
        conditional=True,
    )


@email_ordinaria.route("/<id_email>/segna-letta", methods=["POST"])
@_login_required
def segna_letta(id_email: str):
    _get_gestore().marca_letta(id_email)
    return _json_or_redirect(request.form.get("cartella", "INBOX"))


@email_ordinaria.route("/<id_email>/segna-non-letta", methods=["POST"])
@_login_required
def segna_non_letta(id_email: str):
    _get_gestore().marca_non_letta(id_email)
    return _json_or_redirect(request.form.get("cartella", "INBOX"))


@email_ordinaria.route("/<id_email>/cestino", methods=["POST"])
@_login_required
def cestino(id_email: str):
    _get_gestore().sposta_cestino(id_email)
    return _json_or_redirect(request.form.get("cartella", "INBOX"))


@email_ordinaria.route("/<id_email>/ripristina", methods=["POST"])
@_login_required
def ripristina(id_email: str):
    _get_gestore().ripristina(id_email)
    return _json_or_redirect("INBOX")


@email_ordinaria.route("/<id_email>/elimina", methods=["POST"])
@_login_required
def elimina(id_email: str):
    _get_gestore().elimina_definitivamente(id_email)
    return _json_or_redirect("CESTINO")


@email_ordinaria.route("/svuota-cestino", methods=["POST"])
@_login_required
def svuota_cestino():
    totale = _get_gestore().svuota_cestino()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": True, "messaggio": f"Cestino svuotato: {totale} email eliminate."})
    flash(f"Cestino svuotato ({totale} email eliminate).", "success")
    return redirect(url_for("email_ordinaria.casella", cartella="CESTINO"))


@email_ordinaria.route("/api/stats")
@_login_required
def stats_json():
    gestore = _get_gestore()
    return jsonify(gestore.statistiche())


@email_ordinaria.route("/sincronizza", methods=["POST"])
@_login_required
def sincronizza():
    """Sincronizza la casella ordinaria usando i parametri IMAP del tab SMTP."""
    try:
        return jsonify(run_ordinary_mailbox_sync())
    except TenantDataPathError as exc:
        return jsonify({"ok": False, "errore": str(exc)}), 409
