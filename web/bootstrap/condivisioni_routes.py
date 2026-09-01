"""Sharing and collaboration routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

from pct.condivisione import RuoloCondivisione
from pct.formatting import format_date_it
from web.blueprints.react_shell import render_react_shell_response
from web.services.react_condivisioni_bridge import build_client_collaborators_payload


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

    @app.route("/cartelle-condivise")
    def cartelle_condivise():
        return render_react_shell_response("cartelle-condivise")

    @app.route("/clienti/<id_cliente>/collaboratori", methods=["GET"])
    def gestione_collaboratori(id_cliente: str):
        _ = id_cliente
        return render_react_shell_response("clienti-collaboratori")

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

    def _utente_api_corrente():
        utente = getattr(g, "utente_corrente", None)
        if utente is None:
            return None, (
                jsonify({"errore": "Autenticazione richiesta.", "code": "authentication_required"}),
                401,
            )
        return utente, None

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["GET"])
    def api_condivisioni_cliente(id_cliente: str):
        utente, errore_auth = _utente_api_corrente()
        if errore_auth:
            return errore_auth
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            return jsonify({"errore": "Cliente non trovato."}), 404
        if not cliente_accessibile(id_cliente):
            return jsonify({"errore": "Accesso negato."}), 403
        try:
            return jsonify(
                build_client_collaborators_payload(
                    cliente=cliente,
                    get_condivisioni=get_condivisioni,
                    get_utenti=get_utenti,
                    current_user=utente,
                )
            )
        except Exception as exc:
            app.logger.exception("Errore api_condivisioni_cliente: %s", exc)
            return jsonify({"errore": "Condivisioni cliente non disponibili."}), 503

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni", methods=["POST"])
    def api_aggiungi_collaboratore(id_cliente: str):
        utente, errore_auth = _utente_api_corrente()
        if errore_auth:
            return errore_auth
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            return jsonify({"errore": "Cliente non trovato."}), 404

        puo_gestire = bool(
            utente
            and (
                utente.ha_permesso("clienti.scrivi")
                or get_condivisioni().ha_accesso(
                    utente.id,
                    id_cliente,
                    RuoloCondivisione.GESTORE,
                )
            )
        )
        if not puo_gestire:
            return jsonify({"errore": "Non hai il permesso di gestire questi collaboratori."}), 403

        data = request.get_json(silent=True) or {}
        id_utente = str(data.get("id_utente") or "").strip()
        if not id_utente:
            return jsonify({"errore": "Seleziona un collaboratore."}), 400
        if id_utente == utente.id:
            return jsonify({"errore": "Il profilo in uso non può essere aggiunto come collaboratore."}), 400

        utente_dest = get_utenti().get(id_utente)
        if not utente_dest or not getattr(utente_dest, "attivo", True):
            return jsonify({"errore": "Collaboratore non disponibile."}), 404

        ruolo_str = str(data.get("ruolo") or RuoloCondivisione.LETTURA.value).strip().upper()
        try:
            ruolo = RuoloCondivisione(ruolo_str)
        except ValueError:
            return jsonify({"errore": "Ruolo non valido."}), 400

        data_scadenza = str(data.get("data_scadenza") or "").strip()
        if data_scadenza:
            try:
                if date.fromisoformat(data_scadenza) < date.today():
                    return jsonify({"errore": "La scadenza non può essere nel passato."}), 400
            except ValueError:
                return jsonify({"errore": "La data di scadenza non è valida."}), 400

        note = str(data.get("note") or "").strip()[:1000]
        raw_tags = data.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = raw_tags.split(",")
        if not isinstance(raw_tags, list):
            return jsonify({"errore": "I tag indicati non sono validi."}), 400
        tags = [str(tag).strip()[:50] for tag in raw_tags if str(tag).strip()][:10]

        try:
            get_condivisioni().condividi(
                id_cliente=id_cliente,
                id_utente=utente_dest.id,
                username=utente_dest.username,
                nome_completo=utente_dest.nome_completo or utente_dest.username,
                ruolo=ruolo,
                condiviso_da=utente.username,
                note=note,
                data_scadenza=data_scadenza,
                tags=tags,
            )
        except ValueError as exc:
            return jsonify({"errore": str(exc)}), 400

        audit(
            "condivisione.api.condividi",
            "cliente",
            id_cliente,
            dettagli=f"→ {utente_dest.username} [{ruolo.value}]",
        )
        try:
            sync_manager.pubblica(
                "info",
                "clienti",
                id_cliente,
                utente.username,
                messaggio=f"Cartella condivisa con {utente_dest.username}",
            )
        except Exception:
            app.logger.warning("Sincronizzazione condivisione non pubblicata per %s", id_cliente)
        if utente_dest.email:
            scadenza_label = format_date_it(data_scadenza) if data_scadenza else ""
            try:
                get_messaggi().invia_email(
                    destinatario=utente_dest.email,
                    oggetto=f"Cartella condivisa: {cliente.nome_completo}",
                    corpo_testo=(
                        f"Ciao {utente_dest.nome_completo or utente_dest.username},\n\n"
                        f"{utente.nome_completo or utente.username} ha condiviso con te "
                        f"la cartella cliente di {cliente.nome_completo} con accesso {ruolo.value.lower()}.\n"
                        + (f"L'accesso scade il {scadenza_label}.\n" if scadenza_label else "")
                        + (f"Note: {note}\n" if note else "")
                        + "\nAccedi allo studio per visualizzare la cartella."
                    ),
                    nome_destinatario=utente_dest.nome_completo or utente_dest.username,
                )
            except Exception:
                app.logger.warning("Email condivisione non inviata a %s", utente_dest.username)

        return jsonify(
            {
                "stato": "ok",
                "messaggio": f"{utente_dest.nome_completo or utente_dest.username} è stato aggiunto.",
            }
        ), 201

    @app.route("/api/v1/clienti/<id_cliente>/condivisioni/<id_utente>", methods=["DELETE"])
    def api_revoca_collaboratore(id_cliente: str, id_utente: str):
        utente, errore_auth = _utente_api_corrente()
        if errore_auth:
            return errore_auth
        cliente = get_clienti().get(id_cliente)
        if not cliente:
            return jsonify({"errore": "Cliente non trovato."}), 404

        puo_gestire = bool(
            utente
            and (
                utente.ha_permesso("clienti.scrivi")
                or get_condivisioni().ha_accesso(
                    utente.id,
                    id_cliente,
                    RuoloCondivisione.GESTORE,
                )
            )
        )
        if not puo_gestire:
            return jsonify({"errore": "Non hai il permesso di gestire questi collaboratori."}), 403

        utente_dest = get_utenti().get(id_utente)
        nome_dest = (
            utente_dest.nome_completo or utente_dest.username
            if utente_dest
            else "Collaboratore"
        )
        try:
            if not get_condivisioni().revoca(id_cliente, id_utente):
                return jsonify({"errore": "Accesso non trovato."}), 404
        except Exception as exc:
            app.logger.exception("Errore api_revoca_collaboratore: %s", exc)
            return jsonify({"errore": "Revoca non completata."}), 503

        audit("condivisione.api.revoca", "cliente", id_cliente, dettagli=f"→ {id_utente}")
        try:
            sync_manager.pubblica(
                "info",
                "clienti",
                id_cliente,
                utente.username,
                messaggio=f"Accesso revocato per {nome_dest}",
            )
        except Exception:
            app.logger.warning("Sincronizzazione revoca non pubblicata per %s", id_cliente)
        if utente_dest and utente_dest.email:
            try:
                get_messaggi().invia_email(
                    destinatario=utente_dest.email,
                    oggetto=f"Accesso revocato: {cliente.nome_completo}",
                    corpo_testo=(
                        f"Ciao {nome_dest},\n\n"
                        f"Il tuo accesso alla cartella cliente di {cliente.nome_completo} "
                        f"è stato revocato da {utente.nome_completo or utente.username}."
                    ),
                    nome_destinatario=nome_dest,
                )
            except Exception:
                app.logger.warning("Email revoca non inviata a %s", id_utente)

        return jsonify({"stato": "ok", "messaggio": f"Accesso revocato per {nome_dest}."}), 200

    @app.route("/api/v1/condivisioni/statistiche")
    def api_statistiche_condivisioni():
        utente, errore_auth = _utente_api_corrente()
        if errore_auth:
            return errore_auth
        if not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Permesso insufficiente"}), 403
        try:
            return jsonify(get_condivisioni().statistiche())
        except Exception as exc:
            app.logger.exception("Errore api_statistiche_condivisioni: %s", exc)
            return jsonify({"errore": "Statistiche condivisioni non disponibili."}), 200

    @app.route("/api/v1/condivisioni/pulizia-scaduti", methods=["POST"])
    def api_pulizia_scaduti():
        utente, errore_auth = _utente_api_corrente()
        if errore_auth:
            return errore_auth
        if not utente.ha_permesso("utenti.scrivi"):
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
            return jsonify({"errore": "Pulizia condivisioni scadute non completata."}), 200
