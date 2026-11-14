"""Messaging routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, flash, jsonify, redirect, request, url_for

from pct.clienti import GestioneClienti
from pct.messaggi import CanaleMsggio
from pct.notifiche_wa import safe_wa_link
from web.blueprints.react_shell import render_react_shell_response


def _richiede_json() -> bool:
    return (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or "application/json" in (request.headers.get("Accept") or "")
    )


def register_messages_routes(
    app: Flask,
    *,
    get_messaggi: Callable[[], object],
    get_clienti: Callable[[], GestioneClienti],
) -> None:
    """Register messaging routes and stats API."""

    @app.route("/messaggi")
    def lista_messaggi():
        return render_react_shell_response("messaggi")

    @app.route("/messaggi/nuovo", methods=["GET", "POST"])
    def nuovo_messaggio():
        if request.method == "GET":
            return render_react_shell_response("messaggi/nuovo")

        gm = get_messaggi()
        if request.method == "POST":
            f = request.form
            canale_str = f["canale"]
            canale = CanaleMsggio(canale_str)
            destinatario = f["destinatario"].strip()
            testo = f.get("testo", "").strip()
            oggetto = f.get("oggetto", "").strip()
            id_cliente = f.get("id_cliente", "") or ""
            from_cliente = f.get("from_cliente", "")
            try:
                if canale == CanaleMsggio.EMAIL:
                    gm.invia_email(
                        destinatario=destinatario,
                        oggetto=oggetto,
                        corpo_testo=testo,
                        id_cliente=id_cliente,
                    )
                elif canale == CanaleMsggio.SMS:
                    gm.invia_sms(
                        telefono=destinatario,
                        testo=testo,
                        id_cliente=id_cliente,
                    )
                else:
                    msg_wa = gm.invia_whatsapp(
                        telefono=destinatario,
                        testo=testo,
                        id_cliente=id_cliente,
                    )
                    wa_link = safe_wa_link(msg_wa.sid_esterno)
                    if wa_link:
                        if _richiede_json():
                            target = url_for("cartella_cliente", id_cliente=from_cliente) if from_cliente else url_for("lista_messaggi")
                            return jsonify({"ok": True, "id": msg_wa.id, "message": "Messaggio WhatsApp preparato.", "redirect": target, "whatsappLink": wa_link})
                        # Senza API WhatsApp il messaggio si invia da WhatsApp Web (collegamento verificato).
                        return redirect(wa_link)
                flash("Messaggio inviato.", "success")
                if from_cliente:
                    target = url_for("cartella_cliente", id_cliente=from_cliente)
                    if _richiede_json():
                        return jsonify({"ok": True, "message": "Messaggio inviato.", "redirect": target})
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                target = url_for("lista_messaggi")
                if _richiede_json():
                    return jsonify({"ok": True, "message": "Messaggio inviato.", "redirect": target})
                return redirect(url_for("lista_messaggi"))
            except Exception as e:
                if _richiede_json():
                    return jsonify({"ok": False, "message": str(e)}), 400
                flash(str(e), "danger")
        return redirect(url_for("nuovo_messaggio"))

    @app.route("/messaggi/<id_msg>")
    def dettaglio_messaggio(id_msg):
        gm = get_messaggi()
        msg = gm.get(id_msg)
        if not msg:
            flash("Messaggio non trovato.", "warning")
            return redirect(url_for("lista_messaggi"))
        return render_react_shell_response(f"messaggi/{id_msg}")

    @app.route("/messaggi/<id_msg>/elimina", methods=["POST"])
    def elimina_messaggio(id_msg):
        gm = get_messaggi()
        try:
            gm.elimina(id_msg)
            flash("Messaggio eliminato.", "success")
            if _richiede_json():
                return jsonify({"ok": True, "id": id_msg, "message": "Messaggio eliminato.", "redirect": url_for("lista_messaggi")})
        except ValueError as e:
            if _richiede_json():
                return jsonify({"ok": False, "message": str(e)}), 400
            flash(str(e), "danger")
        return redirect(url_for("lista_messaggi"))

    @app.route("/api/messaggi/statistiche")
    def api_messaggi_statistiche():
        try:
            return jsonify(get_messaggi().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_messaggi_statistiche: %s", e)
            return jsonify({"errore": str(e)})
