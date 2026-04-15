"""Clienti core routes extracted from web.app."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any

from flask import Flask, flash, g, jsonify, redirect, render_template, request, url_for

from pct.clienti import RiferimentoProcedimento, StatoCliente, TipoCliente, TipoDocumento as TipoDocumentoCliente
from pct.condivisione import RuoloCondivisione


def _salva_indirizzo(gc: Any, id_cliente: str, tipo: str, form: Any, prefix: str = "") -> None:
    gc.aggiorna_indirizzo(
        id_cliente,
        tipo,
        via=form.get(f"{prefix}via", ""),
        civico=form.get(f"{prefix}civico", ""),
        cap=form.get(f"{prefix}cap", ""),
        comune=form.get(f"{prefix}comune", ""),
        provincia=form.get(f"{prefix}provincia", ""),
        nazione=form.get(f"{prefix}nazione", "Italia"),
    )


def register_clienti_routes(
    app: Flask,
    *,
    get_clienti: Callable[[], Any],
    get_condivisioni: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_agenda: Callable[[], Any],
    cliente_accessibile: Callable[..., bool],
    track_recente: Callable[..., None],
    sync_pubblica: Callable[..., None],
    audit: Callable[..., None],
) -> None:
    """Register CRUD and API routes for clienti."""

    @app.route("/clienti")
    def lista_clienti():
        gc = get_clienti()
        utente = g.utente_corrente
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "ATTIVO")

        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None

        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)

        if utente and not utente.ha_permesso("clienti.leggi"):
            ids_accessibili = get_condivisioni().ids_clienti_accessibili(utente.id)
            clienti = [cliente for cliente in clienti if cliente.id in ids_accessibili]

        return render_template(
            "clienti/lista.html",
            clienti=clienti,
            stats=gc.statistiche(),
            q=testo,
            tipo_filtro=tipo_f or "",
            stato_filtro=stato_f or "",
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
        )

    @app.route("/clienti/nuovo", methods=["GET", "POST"])
    def nuovo_cliente():
        gc = get_clienti()
        if request.method == "POST":
            form = request.form
            next_url = form.get("next_url", "").strip()
            if next_url and not next_url.startswith("/"):
                next_url = ""
            tipo = TipoCliente(form["tipo"])
            try:
                cliente = gc.nuovo(
                    tipo=tipo,
                    nome=form.get("nome", ""),
                    cognome=form.get("cognome", ""),
                    ragione_sociale=form.get("ragione_sociale", ""),
                    codice_fiscale=form.get("codice_fiscale", "").upper(),
                    partita_iva=form.get("partita_iva", ""),
                    forma_giuridica=form.get("forma_giuridica", ""),
                    data_nascita=form.get("data_nascita", ""),
                    luogo_nascita=form.get("luogo_nascita", ""),
                    provincia_nascita=form.get("provincia_nascita", ""),
                    sesso=form.get("sesso", ""),
                    nazionalita=form.get("nazionalita", "Italiana"),
                    rappresentante_legale=form.get("rappresentante_legale", ""),
                    cf_rappresentante=form.get("cf_rappresentante", "").upper(),
                    avvocato_referente=form.get("avvocato_referente", ""),
                    provenienza=form.get("provenienza", ""),
                    note=form.get("note", ""),
                )
                _salva_indirizzo(gc, cliente.id, "residenza", form)
                _salva_indirizzo(gc, cliente.id, "domicilio", form, prefix="dom_")
                _salva_indirizzo(gc, cliente.id, "sede_legale", form, prefix="sl_")
                gc.aggiorna_recapiti(
                    cliente.id,
                    telefono=form.get("telefono", ""),
                    cellulare=form.get("cellulare", ""),
                    email=form.get("email", ""),
                    pec=form.get("pec", ""),
                    fax=form.get("fax", ""),
                    sito_web=form.get("sito_web", ""),
                )
                flash(f"Cliente '{cliente.nome_completo}' aggiunto.", "success")
                sync_pubblica("crea", "clienti", cliente.id)
                if next_url:
                    return redirect(next_url)
                if form.get("crea_preventivo_iniziale", "1") == "1":
                    return redirect(
                        url_for(
                            "preventivi.wizard",
                            id_cliente=cliente.id,
                            from_page="cliente",
                            entry="iniziale",
                        )
                    )
                return redirect(url_for("dettaglio_cliente", id_cliente=cliente.id))
            except (ValueError, KeyError) as exc:
                flash(str(exc), "danger")

        return render_template(
            "clienti/form.html",
            cliente=None,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumentoCliente),
            next_url=request.args.get("next_url", "").strip(),
        )

    @app.route("/clienti/<id_cliente>")
    def dettaglio_cliente(id_cliente: str):
        gc = get_clienti()
        cliente = gc.get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente):
            flash("Non hai accesso a questa cartella cliente.", "danger")
            return redirect(url_for("lista_clienti"))

        agenda = get_agenda()
        apps_cliente = agenda.cerca(cliente=cliente.nome_completo)
        gcd = get_condivisioni()
        n_collaboratori = gcd.n_collaboratori(id_cliente)
        utente = g.utente_corrente
        ruolo_cond = gcd.ruolo_accesso(utente.id, id_cliente) if utente else None
        if utente and not utente.ha_permesso("clienti.leggi") and ruolo_cond:
            audit(
                "condivisione.accesso",
                "cliente",
                id_cliente,
                dettagli=f"accesso lettura [{ruolo_cond.value}]",
            )
        link_attivi = gcd.link_attivi_per_cliente(id_cliente)
        fascicoli_cliente = [fascicolo for fascicolo in get_fascicoli().tutti() if fascicolo.id_cliente == id_cliente][:5]
        track_recente(
            "cliente",
            id_cliente,
            cliente.nome_completo,
            url_for("dettaglio_cliente", id_cliente=id_cliente),
            "bi-person",
        )
        return render_template(
            "clienti/dettaglio.html",
            cliente=cliente,
            apps_cliente=apps_cliente,
            n_collaboratori=n_collaboratori,
            ruolo_condivisione=ruolo_cond,
            link_attivi=link_attivi,
            fascicoli_cliente=fascicoli_cliente,
        )

    @app.route("/clienti/<id_cliente>/modifica", methods=["GET", "POST"])
    def modifica_cliente(id_cliente: str):
        gc = get_clienti()
        cliente = gc.get(id_cliente)
        if not cliente:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        if not cliente_accessibile(id_cliente, RuoloCondivisione.SCRITTURA):
            flash("Non hai permesso di modificare questa cartella cliente.", "danger")
            return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

        if request.method == "POST":
            form = request.form
            next_url = form.get("next_url", "").strip()
            if next_url and not next_url.startswith("/"):
                next_url = ""
            try:
                gc.aggiorna(
                    id_cliente,
                    nome=form.get("nome", cliente.nome),
                    cognome=form.get("cognome", cliente.cognome),
                    ragione_sociale=form.get("ragione_sociale", cliente.ragione_sociale),
                    codice_fiscale=form.get("codice_fiscale", cliente.codice_fiscale).upper(),
                    partita_iva=form.get("partita_iva", cliente.partita_iva),
                    forma_giuridica=form.get("forma_giuridica", cliente.forma_giuridica),
                    data_nascita=form.get("data_nascita", cliente.data_nascita),
                    luogo_nascita=form.get("luogo_nascita", cliente.luogo_nascita),
                    provincia_nascita=form.get("provincia_nascita", cliente.provincia_nascita),
                    sesso=form.get("sesso", cliente.sesso),
                    nazionalita=form.get("nazionalita", cliente.nazionalita),
                    rappresentante_legale=form.get("rappresentante_legale", cliente.rappresentante_legale),
                    cf_rappresentante=form.get("cf_rappresentante", cliente.cf_rappresentante).upper(),
                    avvocato_referente=form.get("avvocato_referente", cliente.avvocato_referente),
                    provenienza=form.get("provenienza", cliente.provenienza),
                    note=form.get("note", cliente.note),
                    stato=StatoCliente(form.get("stato", cliente.stato.value)),
                )
                _salva_indirizzo(gc, id_cliente, "residenza", form)
                _salva_indirizzo(gc, id_cliente, "domicilio", form, prefix="dom_")
                _salva_indirizzo(gc, id_cliente, "sede_legale", form, prefix="sl_")
                gc.aggiorna_recapiti(
                    id_cliente,
                    telefono=form.get("telefono", ""),
                    cellulare=form.get("cellulare", ""),
                    email=form.get("email", ""),
                    pec=form.get("pec", ""),
                    fax=form.get("fax", ""),
                    sito_web=form.get("sito_web", ""),
                )
                gc.aggiorna_documento(
                    id_cliente,
                    tipo=TipoDocumentoCliente(form.get("doc_tipo", cliente.documento.tipo.value)),
                    numero=form.get("doc_numero", ""),
                    rilasciato_da=form.get("doc_rilasciato_da", ""),
                    data_rilascio=form.get("doc_data_rilascio", ""),
                    data_scadenza=form.get("doc_data_scadenza", ""),
                )
                flash("Cliente aggiornato.", "success")
                sync_pubblica("modifica", "clienti", id_cliente)
                if next_url:
                    return redirect(next_url)
                return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))
            except (ValueError, KeyError) as exc:
                flash(str(exc), "danger")

        return render_template(
            "clienti/form.html",
            cliente=cliente,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumentoCliente),
            next_url=request.args.get("next_url", "").strip(),
        )

    @app.route("/clienti/<id_cliente>/elimina", methods=["POST"])
    def elimina_cliente(id_cliente: str):
        gc = get_clienti()
        try:
            gc.elimina(id_cliente)
            flash("Cliente eliminato.", "success")
            sync_pubblica("elimina", "clienti", id_cliente)
        except KeyError as exc:
            flash(str(exc), "danger")
        return redirect(url_for("lista_clienti"))

    @app.route("/clienti/<id_cliente>/procedimento", methods=["POST"])
    def aggiungi_procedimento(id_cliente: str):
        gc = get_clienti()
        form = request.form
        try:
            procedimento = RiferimentoProcedimento(
                numero_rg=form["numero_rg"],
                anno=int(form.get("anno", datetime.now().year)),
                tribunale=form.get("tribunale", ""),
                descrizione=form.get("descrizione", ""),
                data_apertura=form.get("data_apertura", date.today().isoformat()),
            )
            gc.aggiungi_procedimento(id_cliente, procedimento)
            flash("Procedimento aggiunto.", "success")
        except (ValueError, KeyError) as exc:
            flash(str(exc), "danger")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    @app.route("/api/clienti")
    def api_clienti():
        try:
            gc = get_clienti()
            query = request.args.get("q", "")
            clienti = gc.cerca(testo=query) if query else gc.tutti()
            return jsonify([cliente.to_dict() for cliente in clienti])
        except Exception as exc:
            app.logger.exception("Errore api_clienti: %s", exc)
            return jsonify([])

    @app.route("/api/clienti/<id_cliente>")
    def api_cliente(id_cliente: str):
        try:
            cliente = get_clienti().get(id_cliente)
            if not cliente:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(cliente.to_dict())
        except Exception as exc:
            app.logger.exception("Errore api_cliente: %s", exc)
            return jsonify({"errore": str(exc)})

    @app.route("/api/clienti/statistiche")
    def api_clienti_statistiche():
        try:
            return jsonify(get_clienti().statistiche())
        except Exception as exc:
            app.logger.exception("Errore api_clienti_statistiche: %s", exc)
            return jsonify({"errore": str(exc)})
