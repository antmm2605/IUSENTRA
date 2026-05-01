"""Casella email ordinaria per IUSENTRA.

La PEC resta sul repository ``EMAIL_CASELLA_DB``. Questa blueprint gestisce
solo posta ordinaria su ``EMAIL_ORDINARIA_DB`` e usa i parametri del tab
``Impostazioni -> Email SMTP`` per ricezione IMAP e invio SMTP.
"""

from __future__ import annotations

import mimetypes
import os
from functools import wraps
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    request,
    send_file,
    url_for,
)

from web.blueprints.react_shell import render_react_shell_response

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


def _cfg_path(key: str, default: str = "", *aliases: str) -> str:
    paths = getattr(g, "data_paths", {}) or {}
    for candidate in (key, *aliases):
        value = paths.get(candidate)
        if value:
            return str(value)
    for candidate in (key, *aliases):
        value = current_app.config.get(candidate)
        if value:
            return str(value)
    return str(default or "")


def _studio_config_path() -> str:
    return _cfg_path("STUDIO_CONFIG", "./config/studio.json", "CONFIG_STUDIO_DB")


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


@email_ordinaria.route("/messaggio/<id_email>")
@_login_required
def dettaglio(id_email: str):
    if not _legacy_requested():
        return render_react_shell_response(f"email-ordinaria/messaggio/{id_email}")
    return redirect(url_for("email_client.dettaglio", id_email=id_email))


@email_ordinaria.route("/messaggio/<id_email>/allegato/<int:indice_allegato>")
@_login_required
def allegato(id_email: str, indice_allegato: int):
    gestore = _get_gestore()
    email_obj = gestore.get(id_email)
    if not email_obj:
        abort(404)
    percorso = gestore.percorso_allegato(email_obj, indice_allegato)
    if not percorso:
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
    gestore = _get_gestore()
    cfg = _get_config_smtp()
    if not cfg or not getattr(cfg, "imap_host", "") or not getattr(cfg, "username", ""):
        return jsonify(
            {
                "ok": False,
                "errore": (
                    "IMAP email ordinaria non configurato. Apri Impostazioni -> Email SMTP "
                    "e compila server IMAP, username e password."
                ),
            }
        )
    try:
        from pct.email_client import cartelle_imap_standard

        report = gestore.sincronizza_imap(
            imap_host=getattr(cfg, "imap_host", ""),
            imap_port=int(getattr(cfg, "imap_port", 993) or 993),
            username=getattr(cfg, "username", ""),
            password=getattr(cfg, "password", ""),
            use_ssl=bool(getattr(cfg, "imap_use_ssl", True)),
            cartelle_imap=cartelle_imap_standard(),
            limite=500,
            timeout_seconds=15,
        )
        _sync_inviati(gestore)
        errore = str(report.get("errore", "") or "").strip()
        return jsonify(
            {
                "ok": True,
                "warning": bool(errore),
                "messaggio": "Sincronizzazione email ordinaria completata con avvisi." if errore else "Sincronizzazione email ordinaria completata.",
                "nuove": report.get("nuove", 0),
                "allegati_salvati": report.get("allegati_salvati", 0),
                "errore": errore,
                "sync_errore": errore,
                "stats": gestore.statistiche(),
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "errore": str(exc)})
