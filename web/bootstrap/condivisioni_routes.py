"""Sharing and collaboration routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

from pct.condivisione import RuoloCondivisione
from web.blueprints.react_shell import render_react_shell_response


def register_condivisioni_routes(
    app: Flask,
    *,
    get_condivisioni: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_utenti: Callable[[], Any],
    get_messaggi: Callable[[], Any],
    cliente_accessibile: Callable[..., bool],
    audit: Callable[..., None],
    sync_manager: Any,
) -> None:
    """Register sharing routes for clienti and fascicoli."""

    def _richiede_vista_classica() -> bool:
        return request.args.get("_legacy") == "1"

    @app.route("/cartelle-condivise")
    def cartelle_condivise():
        if not _richiede_vista_classica():
            return render_react_shell_response("cartelle-condivise")

        utente = g.utente_corrente
        gcd = get_condivisioni()
        gc = get_clienti()

        if utente.ha_permesso("clienti.leggi"):
            accessi_da_me = [
                (gc.get(id_cliente), accesso)
                for id_cliente, accesso in gcd.cartelle_condivise_con(utente.id)
                if gc.get(id_cliente)
            ]
            cartelle_gestite = [
                (cliente, gcd.collaboratori_di(cliente.id))
                for cliente in gc.tutti(stato=None)
                if gcd.n_collaboratori(cliente.id) > 0
            ]
            return render_template(
                "clienti/cartelle_condivise.html",
                modalita="gestore",
                cartelle_gestite=cartelle_gestite,
                accessi_da_me=accessi_da_me,
                stats=gcd.statistiche(),
            )

        cartelle = [
            (gc.get(id_cliente), accesso)
            for id_cliente, accesso in gcd.cartelle_condivise_con(utente.id)
            if gc.get(id_cliente)
        ]
        return render_template(
            "clienti/cartelle_condivise.html",
            modalita="collaboratore",
            cartelle=cartelle,
            stats=gcd.statistiche(),
        )

    @app.route("/clienti/<id_cliente>/collaboratori", methods=["GET", "POST"])
    def gestione_collaboratori(id_cliente: str):
        gc = get_clienti()
        cliente = gc.get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        utente = g.utente_corrente
        puo_gestire = utente.ha_permesso("clienti.scrivi") or get_condivisioni().ha_accesso(
            utente.id,
            id_cliente,
            RuoloCondivisione.GESTORE,
        )
        if not puo_gestire:
            flash("Non hai il permesso di gestire i collaboratori di questa cartella.", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

        gcd = get_condivisioni()
        gu = get_utenti()

        if request.method == "POST":
            azione = request.form.get("azione", "condividi")

            if azione == "condividi":
                id_dest = request.form.get("id_utente", "").strip()
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                note = request.form.get("note", "").strip()
                data_scadenza = request.form.get("data_scadenza", "").strip()
                tags = [tag.strip() for tag in request.form.get("tags", "").strip().split(",") if tag.strip()]
                utente_dest = gu.get(id_dest)
                if not utente_dest:
                    flash("Utente non trovato.", "danger")
                else:
                    try:
                        gcd.condividi(
                            id_cliente=id_cliente,
                            id_utente=utente_dest.id,
                            username=utente_dest.username,
                            nome_completo=utente_dest.nome_completo or utente_dest.username,
                            ruolo=RuoloCondivisione(ruolo_str),
                            condiviso_da=utente.username,
                            note=note,
                            data_scadenza=data_scadenza,
                            tags=tags,
                        )
                        flash(
                            f"Cartella condivisa con {utente_dest.username} ({RuoloCondivisione(ruolo_str).value}).",
                            "success",
                        )
                        audit(
                            "condivisione.condividi",
                            "cliente",
                            id_cliente,
                            dettagli=f"→ {utente_dest.username} [{ruolo_str}]"
                            + (f" scade {data_scadenza}" if data_scadenza else ""),
                        )
                        sync_manager.pubblica(
                            "info",
                            "clienti",
                            id_cliente,
                            utente.username,
                            messaggio=f"Cartella condivisa con {utente_dest.username}",
                        )
                        if utente_dest.email:
                            try:
                                get_messaggi().invia_email(
                                    destinatario=utente_dest.email,
                                    oggetto=f"Cartella condivisa: {cliente.nome_completo}",
                                    corpo_testo=(
                                        f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                                        f"{utente.nome_completo or utente.username} ha condiviso con te "
                                        f"la cartella cliente di {cliente.nome_completo} "
                                        f"con accesso {RuoloCondivisione(ruolo_str).value}.\n"
                                        + (f"L'accesso scade il {data_scadenza}.\n" if data_scadenza else "")
                                        + (f"Note: {note}\n" if note else "")
                                        + "\nAccedi allo studio per visualizzare la cartella."
                                    ),
                                    nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                                )
                            except Exception:
                                pass
                    except ValueError as exc:
                        flash(str(exc), "danger")

            elif azione == "revoca":
                id_dest = request.form.get("id_utente", "").strip()
                utente_dest = gu.get(id_dest)
                username_dest = utente_dest.username if utente_dest else id_dest
                if gcd.revoca(id_cliente, id_dest):
                    flash(f"Accesso revocato per {username_dest}.", "success")
                    audit("condivisione.revoca", "cliente", id_cliente, dettagli=f"→ {username_dest}")
                    sync_manager.pubblica(
                        "info",
                        "clienti",
                        id_cliente,
                        utente.username,
                        messaggio=f"Accesso revocato per {username_dest}",
                    )
                    if utente_dest and utente_dest.email:
                        try:
                            get_messaggi().invia_email(
                                destinatario=utente_dest.email,
                                oggetto=f"Accesso revocato: {cliente.nome_completo}",
                                corpo_testo=(
                                    f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                                    f"Il tuo accesso alla cartella cliente di {cliente.nome_completo} "
                                    f"è stato revocato da {utente.nome_completo or utente.username}."
                                ),
                                nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                            )
                        except Exception:
                            pass
                else:
                    flash("Accesso non trovato.", "warning")

            elif azione == "crea_link":
                ore = int(request.form.get("ore_validita", 72))
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                monouso = request.form.get("monouso") == "1"
                descrizione = request.form.get("descrizione", "").strip()
                token, link = gcd.crea_link_temporaneo(
                    id_cliente=id_cliente,
                    creato_da=utente.username,
                    ruolo=RuoloCondivisione(ruolo_str),
                    ore_validita=ore,
                    monouso=monouso,
                    descrizione=descrizione,
                )
                audit(
                    "condivisione.link_creato",
                    "cliente",
                    id_cliente,
                    dettagli=f"link {link.id} [{ruolo_str}] {ore}h",
                )
                link_url = url_for("accesso_link_temporaneo", token=token, _external=True)
                flash("Link creato (valido {ore}h). Copialo e invialo al destinatario.".format(ore=ore), "success")
                collaboratori = gcd.collaboratori_di(id_cliente)
                ids_collaboratori = {accesso.id_utente for accesso in collaboratori}
                tutti_utenti = [
                    utente_item
                    for utente_item in gu.tutti(solo_attivi=True)
                    if utente_item.id != utente.id and utente_item.id not in ids_collaboratori
                ]
                return render_template(
                    "clienti/collaboratori.html",
                    cliente=cliente,
                    collaboratori=collaboratori,
                    utenti_disponibili=tutti_utenti,
                    ruoli_condivisione=list(RuoloCondivisione),
                    link_temporanei=gcd.link_attivi_per_cliente(id_cliente),
                    nuovo_link_url=link_url,
                )

            elif azione == "revoca_link":
                id_link = request.form.get("id_link", "").strip()
                if gcd.revoca_link_temporaneo(id_link):
                    flash("Link revocato.", "success")
                    audit("condivisione.link_revocato", "cliente", id_cliente, dettagli=f"link {id_link}")
                else:
                    flash("Link non trovato.", "warning")

            return redirect(url_for("gestione_collaboratori", id_cliente=id_cliente))

        collaboratori = gcd.collaboratori_di(id_cliente)
        ids_collaboratori = {accesso.id_utente for accesso in collaboratori}
        tutti_utenti = [
            utente_item
            for utente_item in gu.tutti(solo_attivi=True)
            if utente_item.id != utente.id and utente_item.id not in ids_collaboratori
        ]
        return render_template(
            "clienti/collaboratori.html",
            cliente=cliente,
            collaboratori=collaboratori,
            utenti_disponibili=tutti_utenti,
            ruoli_condivisione=list(RuoloCondivisione),
            link_temporanei=gcd.link_attivi_per_cliente(id_cliente),
            nuovo_link_url=None,
        )

    @app.route("/accesso/<token>")
    def accesso_link_temporaneo(token: str):
        gcd = get_condivisioni()
        link = gcd.verifica_link_temporaneo(token)
        if not link:
            return render_template("clienti/link_scaduto.html"), 410

        cliente = get_clienti().get(link.id_cliente)
        if not cliente:
            return render_template("clienti/link_scaduto.html"), 404

        fascicolo = get_fascicoli().get(link.id_fascicolo) if link.id_fascicolo else None
        audit(
            "condivisione.link_accesso",
            "cliente",
            link.id_cliente,
            dettagli=f"link {link.id} desc={link.descrizione}",
        )
        return render_template(
            "clienti/link_temporaneo.html",
            cliente=cliente,
            fascicolo=fascicolo,
            link=link,
            ruolo=link.ruolo,
        )

    @app.route("/fascicoli/<id_fasc>/collaboratori", methods=["GET", "POST"])
    def gestione_collaboratori_fascicolo(id_fasc: str):
        fascicolo = get_fascicoli().get(id_fasc)
        if not fascicolo:
            flash("Fascicolo non trovato.", "warning")
            return redirect(url_for("lista_fascicoli"))

        utente = g.utente_corrente
        puo_gestire = utente.ha_permesso("fascicoli.scrivi") or get_condivisioni().ha_accesso_fascicolo(
            utente.id,
            id_fasc,
            RuoloCondivisione.GESTORE,
        )
        if not puo_gestire:
            flash("Non hai il permesso di gestire i collaboratori di questo fascicolo.", "danger")
            return redirect(url_for("dettaglio_fascicolo", id_fasc=id_fasc))

        gcd = get_condivisioni()
        gu = get_utenti()

        if request.method == "POST":
            azione = request.form.get("azione", "condividi")
            id_dest = request.form.get("id_utente", "").strip()
            utente_dest = gu.get(id_dest)

            if azione == "condividi" and utente_dest:
                ruolo_str = request.form.get("ruolo", RuoloCondivisione.LETTURA.value)
                gcd.condividi_fascicolo(
                    id_fascicolo=id_fasc,
                    id_cliente=fascicolo.id_cliente,
                    id_utente=utente_dest.id,
                    username=utente_dest.username,
                    nome_completo=utente_dest.nome_completo or utente_dest.username,
                    ruolo=RuoloCondivisione(ruolo_str),
                    condiviso_da=utente.username,
                    note=request.form.get("note", "").strip(),
                    data_scadenza=request.form.get("data_scadenza", "").strip(),
                    tags=[tag.strip() for tag in request.form.get("tags", "").split(",") if tag.strip()],
                )
                flash(f"Fascicolo condiviso con {utente_dest.username}.", "success")
                audit(
                    "condivisione.fascicolo.condividi",
                    "fascicolo",
                    id_fasc,
                    dettagli=f"→ {utente_dest.username} [{ruolo_str}]",
                )
            elif azione == "revoca":
                username_dest = utente_dest.username if utente_dest else id_dest
                if gcd.revoca_fascicolo(id_fasc, id_dest):
                    flash(f"Accesso fascicolo revocato per {username_dest}.", "success")
                    audit(
                        "condivisione.fascicolo.revoca",
                        "fascicolo",
                        id_fasc,
                        dettagli=f"→ {username_dest}",
                    )
                else:
                    flash("Accesso non trovato.", "warning")
            return redirect(url_for("gestione_collaboratori_fascicolo", id_fasc=id_fasc))

        collaboratori = gcd.collaboratori_fascicolo(id_fasc)
        ids_collaboratori = {accesso.id_utente for accesso in collaboratori}
        tutti_utenti = [
            utente_item
            for utente_item in gu.tutti(solo_attivi=True)
            if utente_item.id != utente.id and utente_item.id not in ids_collaboratori
        ]
        return render_template(
            "fascicoli/collaboratori_fascicolo.html",
            fascicolo=fascicolo,
            collaboratori=collaboratori,
            utenti_disponibili=tutti_utenti,
            ruoli_condivisione=list(RuoloCondivisione),
        )

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["GET"])
    def api_condivisioni_cliente(id_cliente: str):
        if not cliente_accessibile(id_cliente):
            return jsonify({"errore": "Accesso negato"}), 403
        try:
            gcd = get_condivisioni()
            collaboratori = gcd.collaboratori_di(id_cliente)
            return jsonify(
                {
                    "id_cliente": id_cliente,
                    "collaboratori": [accesso.to_dict() for accesso in collaboratori],
                    "n_collaboratori": len(collaboratori),
                    "link_attivi": len(gcd.link_attivi_per_cliente(id_cliente)),
                    "statistiche": gcd.statistiche(),
                }
            )
        except Exception as exc:
            app.logger.exception("Errore api_condivisioni_cliente: %s", exc)
            return jsonify({"errore": str(exc)})

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["POST"])
    def api_aggiungi_collaboratore(id_cliente: str):
        utente = g.utente_corrente
        puo = utente and (
            utente.ha_permesso("clienti.scrivi")
            or get_condivisioni().ha_accesso(utente.id, id_cliente, RuoloCondivisione.GESTORE)
        )
        if not puo:
            return jsonify({"errore": "Permesso insufficiente"}), 403

        data = request.get_json(silent=True) or {}
        utente_dest = get_utenti().get(data.get("id_utente", ""))
        if not utente_dest:
            return jsonify({"errore": "Utente non trovato"}), 404

        ruolo_str = data.get("ruolo", RuoloCondivisione.LETTURA.value)
        try:
            ruolo = RuoloCondivisione(ruolo_str)
        except ValueError:
            return jsonify({"errore": f"Ruolo '{ruolo_str}' non valido"}), 400

        get_condivisioni().condividi(
            id_cliente=id_cliente,
            id_utente=utente_dest.id,
            username=utente_dest.username,
            nome_completo=utente_dest.nome_completo or utente_dest.username,
            ruolo=ruolo,
            condiviso_da=utente.username,
            note=data.get("note", ""),
            data_scadenza=data.get("data_scadenza", ""),
            tags=data.get("tags", []),
        )
        audit("condivisione.api.condividi", "cliente", id_cliente, dettagli=f"→ {utente_dest.username} [{ruolo_str}]")
        return jsonify({"stato": "ok", "username": utente_dest.username, "ruolo": ruolo_str}), 201

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni/<id_utente>", methods=["DELETE"])
    def api_revoca_collaboratore(id_cliente: str, id_utente: str):
        utente = g.utente_corrente
        puo = utente and (
            utente.ha_permesso("clienti.scrivi")
            or get_condivisioni().ha_accesso(utente.id, id_cliente, RuoloCondivisione.GESTORE)
        )
        if not puo:
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            if get_condivisioni().revoca(id_cliente, id_utente):
                audit("condivisione.api.revoca", "cliente", id_cliente, dettagli=f"→ {id_utente}")
                return jsonify({"stato": "ok"}), 200
            return jsonify({"errore": "Accesso non trovato"}), 404
        except Exception as exc:
            app.logger.exception("Errore api_revoca_collaboratore: %s", exc)
            return jsonify({"errore": str(exc)})

    @app.route("/api/v1/condivisioni/statistiche")
    def api_statistiche_condivisioni():
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            return jsonify(get_condivisioni().statistiche())
        except Exception as exc:
            app.logger.exception("Errore api_statistiche_condivisioni: %s", exc)
            return jsonify({"errore": str(exc)})

    @app.route("/api/v1/condivisioni/pulizia-scaduti", methods=["POST"])
    def api_pulizia_scaduti():
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.scrivi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            gcd = get_condivisioni()
            n_scaduti = gcd.revoca_scaduti()
            n_link = gcd.pulisci_link_scaduti()
            audit(
                "condivisione.pulizia",
                "sistema",
                "",
                dettagli=f"rimossi {n_scaduti} accessi + {n_link} link scaduti",
            )
            return jsonify({"accessi_rimossi": n_scaduti, "link_rimossi": n_link})
        except Exception as exc:
            app.logger.exception("Errore api_pulizia_scaduti: %s", exc)
            return jsonify({"errore": str(exc)})
