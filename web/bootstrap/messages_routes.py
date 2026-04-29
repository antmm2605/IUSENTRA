"""Messaging routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from pct.clienti import GestioneClienti
from pct.messaggi import CanaleMsggio, StatoMessaggio, TipoAutomazione
from web.blueprints.react_shell import render_react_shell_response


def _richiede_vista_classica() -> bool:
    return request.args.get("_legacy") == "1"


def register_messages_routes(
    app: Flask,
    *,
    get_messaggi: Callable[[], object],
    get_clienti: Callable[[], GestioneClienti],
) -> None:
    """Register messaging routes and stats API."""

    @app.route("/messaggi")
    def lista_messaggi():
        if not _richiede_vista_classica():
            return render_react_shell_response("messaggi")

        gm = get_messaggi()
        canale = request.args.get("canale", "")
        stato = request.args.get("stato", "")
        q = request.args.get("q", "")
        messaggi = gm.tutti(
            canale=CanaleMsggio(canale) if canale else None,
            stato=StatoMessaggio(stato) if stato else None,
        )
        if q:
            ql = q.lower()
            messaggi = [
                m
                for m in messaggi
                if ql in (m.email_destinatario or m.telefono_destinatario or "").lower()
                or ql in m.nome_destinatario.lower()
                or ql in m.oggetto.lower()
                or ql in m.corpo.lower()
            ]
        return render_template(
            "messaggi/lista.html",
            messaggi=messaggi,
            canali=list(CanaleMsggio),
            stati=list(StatoMessaggio),
            canale=canale,
            stato=stato,
            q=q,
            stats=gm.statistiche(),
        )

    @app.route("/messaggi/nuovo", methods=["GET", "POST"])
    def nuovo_messaggio():
        if request.method == "GET" and not _richiede_vista_classica():
            return render_react_shell_response("messaggi/nuovo")

        gm = get_messaggi()
        gc = get_clienti()
        clienti = gc.tutti()
        ha_wa_api = bool(app.config.get("TWILIO_SID") and app.config.get("TWILIO_TOKEN"))
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
                    if msg_wa.sid_esterno and msg_wa.sid_esterno.startswith("https://wa.me"):
                        return render_template(
                            "messaggi/form.html",
                            clienti=clienti,
                            canali=list(CanaleMsggio),
                            tipi_automazione=list(TipoAutomazione),
                            id_cliente=id_cliente,
                            canale_default="WHATSAPP",
                            from_cliente=from_cliente,
                            cliente_presel=gc.get(id_cliente) if id_cliente else None,
                            ha_wa_api=ha_wa_api,
                            wa_link=msg_wa.sid_esterno,
                        )
                flash("Messaggio inviato.", "success")
                if from_cliente:
                    return redirect(url_for("cartella_cliente", id_cliente=from_cliente))
                return redirect(url_for("lista_messaggi"))
            except Exception as e:
                flash(str(e), "danger")
        id_cliente_get = request.args.get("id_cliente", "")
        canale_get = request.args.get("canale", "EMAIL")
        from_cliente_get = request.args.get("from_cliente", "")
        cliente_presel = gc.get(id_cliente_get) if id_cliente_get else None
        return render_template(
            "messaggi/form.html",
            clienti=clienti,
            canali=list(CanaleMsggio),
            tipi_automazione=list(TipoAutomazione),
            id_cliente=id_cliente_get,
            canale_default=canale_get,
            from_cliente=from_cliente_get,
            cliente_presel=cliente_presel,
            ha_wa_api=ha_wa_api,
        )

    @app.route("/messaggi/<id_msg>")
    def dettaglio_messaggio(id_msg):
        gm = get_messaggi()
        msg = gm.get(id_msg)
        if not msg:
            flash("Messaggio non trovato.", "warning")
            return redirect(url_for("lista_messaggi"))
        return render_template("messaggi/dettaglio.html", msg=msg)

    @app.route("/messaggi/<id_msg>/elimina", methods=["POST"])
    def elimina_messaggio(id_msg):
        gm = get_messaggi()
        try:
            gm.elimina(id_msg)
            flash("Messaggio eliminato.", "success")
        except ValueError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_messaggi"))

    @app.route("/api/messaggi/statistiche")
    def api_messaggi_statistiche():
        try:
            return jsonify(get_messaggi().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_messaggi_statistiche: %s", e)
            return jsonify({"errore": str(e)})
