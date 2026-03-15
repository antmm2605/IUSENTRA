"""
Flask web application — Studio Legale PCT.

Avvio:
    python -m web
    oppure: flask --app web.app run --debug
"""

import os
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)

from pct.agenda import (
    Agenda,
    TipoAppuntamento,
    StatoAppuntamento,
)
from pct.reginde import ClientReGINde
from pct.clienti import (
    GestioneClienti,
    Cliente,
    TipoCliente,
    StatoCliente,
    TipoDocumento,
    Indirizzo,
    Recapiti,
    DocumentoIdentita,
    RiferimentoProcedimento,
)

# ------------------------------------------------------------------ factory

def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = os.getenv("PCT_SECRET_KEY", "dev-secret-pct-2024")

    cfg = config or {}
    app.config["AGENDA_DB"] = cfg.get(
        "AGENDA_DB", os.getenv("PCT_AGENDA_DB", "./agenda/appuntamenti.json")
    )
    app.config["CLIENTI_DB"] = cfg.get(
        "CLIENTI_DB", os.getenv("PCT_CLIENTI_DB", "./clienti/anagrafica.json")
    )

    def get_agenda() -> Agenda:
        return Agenda(db_path=app.config["AGENDA_DB"])

    def get_clienti() -> GestioneClienti:
        return GestioneClienti(db_path=app.config["CLIENTI_DB"])

    # ---------------------------------------------------------------- context

    @app.template_filter("fmt_data")
    def fmt_data(val: str) -> str:
        if not val:
            return "—"
        try:
            from datetime import date
            d = date.fromisoformat(val[:10])
            return d.strftime("%d/%m/%Y")
        except ValueError:
            return val

    @app.context_processor
    def inject_globals():
        return {
            "oggi": date.today(),
            "ora_adesso": datetime.now().strftime("%H:%M"),
            "TipoAppuntamento": TipoAppuntamento,
            "StatoAppuntamento": StatoAppuntamento,
            "TipoCliente": TipoCliente,
            "StatoCliente": StatoCliente,
        }

    # ---------------------------------------------------------------- dashboard

    @app.route("/")
    def dashboard():
        agenda = get_agenda()
        oggi = date.today()
        apps_oggi = agenda.per_giorno(oggi)
        apps_settimana = agenda.per_settimana(oggi)
        reminder = agenda.prossimi_reminder(entro_minuti=120)
        stats = agenda.statistiche()
        return render_template(
            "dashboard.html",
            apps_oggi=apps_oggi,
            apps_settimana=apps_settimana,
            reminder=reminder,
            stats=stats,
        )

    # ---------------------------------------------------------------- agenda

    @app.route("/agenda")
    def agenda_view():
        agenda = get_agenda()
        vista = request.args.get("vista", "settimana")
        oggi = date.today()

        # navigazione settimana / mese
        offset = int(request.args.get("offset", 0))

        if vista == "giorno":
            giorno = oggi + timedelta(days=offset)
            apps = agenda.per_giorno(giorno)
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                giorno=giorno,
                offset=offset,
            )

        if vista == "mese":
            # offset in mesi
            anno = oggi.year
            mese = oggi.month + offset
            while mese > 12:
                mese -= 12
                anno += 1
            while mese < 1:
                mese += 12
                anno -= 1
            apps = agenda.per_mese(anno, mese)
            primo = date(anno, mese, 1)
            # padding giorni iniziali per griglia
            pad = primo.weekday()  # lunedì=0
            import calendar
            giorni_mese = calendar.monthrange(anno, mese)[1]
            return render_template(
                "agenda.html",
                vista=vista,
                apps=apps,
                anno=anno,
                mese=mese,
                primo=primo,
                pad=pad,
                giorni_mese=giorni_mese,
                offset=offset,
                nomi_mesi=[
                    "", "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio",
                    "Giugno", "Luglio", "Agosto", "Settembre", "Ottobre",
                    "Novembre", "Dicembre",
                ],
            )

        # default: settimana
        inizio = oggi + timedelta(weeks=offset) - timedelta(days=oggi.weekday())
        fine = inizio + timedelta(days=6)
        apps = agenda.per_settimana(inizio)
        giorni = [inizio + timedelta(days=i) for i in range(7)]
        apps_per_giorno = {g: [a for a in apps if a.data_ora_dt.date() == g] for g in giorni}
        return render_template(
            "agenda.html",
            vista=vista,
            apps=apps,
            apps_per_giorno=apps_per_giorno,
            giorni=giorni,
            inizio=inizio,
            fine=fine,
            offset=offset,
        )

    @app.route("/agenda/nuovo", methods=["GET", "POST"])
    def nuovo_appuntamento():
        if request.method == "POST":
            agenda = get_agenda()
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            data_ora = f"{data}T{ora}:00" if data else ""
            try:
                app = agenda.aggiungi(
                    titolo=request.form["titolo"],
                    tipo=TipoAppuntamento(request.form["tipo"]),
                    data_ora=data_ora,
                    durata_minuti=int(request.form.get("durata", 60)),
                    luogo=request.form.get("luogo", ""),
                    cliente=request.form.get("cliente", ""),
                    cf_cliente=request.form.get("cf_cliente", ""),
                    procedimento=request.form.get("procedimento", ""),
                    tribunale=request.form.get("tribunale", ""),
                    avvocato=request.form.get("avvocato", ""),
                    note=request.form.get("note", ""),
                    reminder_minuti=int(request.form.get("reminder", 60)),
                )
                flash(f"Appuntamento '{app.titolo}' aggiunto.", "success")
                return redirect(url_for("dettaglio_appuntamento", id_app=app.id))
            except ValueError as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        tribunali = reginde.elenca_uffici()
        return render_template(
            "form_appuntamento.html",
            app=None,
            tipi=list(TipoAppuntamento),
            tribunali=tribunali,
        )

    @app.route("/agenda/<id_app>")
    def dettaglio_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))
        return render_template("dettaglio_appuntamento.html", app=app)

    @app.route("/agenda/<id_app>/modifica", methods=["GET", "POST"])
    def modifica_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            flash("Appuntamento non trovato.", "warning")
            return redirect(url_for("agenda_view"))

        if request.method == "POST":
            data = request.form.get("data", "")
            ora = request.form.get("ora", "09:00")
            campi = {
                "titolo": request.form["titolo"],
                "tipo": TipoAppuntamento(request.form["tipo"]),
                "data_ora": f"{data}T{ora}:00" if data else app.data_ora,
                "durata_minuti": int(request.form.get("durata", app.durata_minuti)),
                "luogo": request.form.get("luogo", ""),
                "cliente": request.form.get("cliente", ""),
                "cf_cliente": request.form.get("cf_cliente", ""),
                "procedimento": request.form.get("procedimento", ""),
                "tribunale": request.form.get("tribunale", ""),
                "avvocato": request.form.get("avvocato", ""),
                "note": request.form.get("note", ""),
                "reminder_minuti": int(request.form.get("reminder", app.reminder_minuti)),
            }
            try:
                agenda.modifica(id_app, **campi)
                flash("Appuntamento aggiornato.", "success")
                return redirect(url_for("dettaglio_appuntamento", id_app=id_app))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        tribunali = reginde.elenca_uffici()
        return render_template(
            "form_appuntamento.html",
            app=app,
            tipi=list(TipoAppuntamento),
            tribunali=tribunali,
        )

    @app.route("/agenda/<id_app>/stato", methods=["POST"])
    def cambia_stato(id_app):
        agenda = get_agenda()
        nuovo = request.form.get("stato")
        try:
            agenda.cambia_stato(id_app, StatoAppuntamento(nuovo))
            flash("Stato aggiornato.", "success")
        except (KeyError, ValueError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_appuntamento", id_app=id_app))

    @app.route("/agenda/<id_app>/elimina", methods=["POST"])
    def elimina_appuntamento(id_app):
        agenda = get_agenda()
        try:
            agenda.elimina(id_app)
            flash("Appuntamento eliminato.", "success")
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("agenda_view"))

    # ---------------------------------------------------------------- API JSON

    @app.route("/api/agenda")
    def api_agenda():
        agenda = get_agenda()
        da_str = request.args.get("da")
        a_str = request.args.get("a")
        da = date.fromisoformat(da_str) if da_str else None
        a = date.fromisoformat(a_str) if a_str else None
        apps = agenda.cerca(da=da, a=a)
        return jsonify([a.to_dict() for a in apps])

    @app.route("/api/agenda/<id_app>")
    def api_appuntamento(id_app):
        agenda = get_agenda()
        app = agenda.get(id_app)
        if not app:
            return jsonify({"errore": "Non trovato"}), 404
        return jsonify(app.to_dict())

    @app.route("/api/reminder")
    def api_reminder():
        agenda = get_agenda()
        entro = int(request.args.get("entro", 60))
        apps = agenda.prossimi_reminder(entro_minuti=entro)
        return jsonify([a.to_dict() for a in apps])

    @app.route("/api/statistiche")
    def api_statistiche():
        return jsonify(get_agenda().statistiche())

    # ---------------------------------------------------------------- tribunali

    @app.route("/tribunali")
    def tribunali():
        reginde = ClientReGINde()
        uffici = reginde.elenca_uffici()
        return render_template("tribunali.html", uffici=uffici)

    # ================================================================ CLIENTI

    @app.route("/clienti")
    def lista_clienti():
        gc = get_clienti()
        testo = request.args.get("q", "").strip()
        tipo_f = request.args.get("tipo")
        stato_f = request.args.get("stato", "ATTIVO")

        tipo = TipoCliente(tipo_f) if tipo_f else None
        stato = StatoCliente(stato_f) if stato_f else None

        clienti = gc.cerca(testo=testo, tipo=tipo, stato=stato) if testo else gc.tutti(stato=stato, tipo=tipo)
        stats = gc.statistiche()
        return render_template(
            "clienti/lista.html",
            clienti=clienti,
            stats=stats,
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
            f = request.form
            tipo = TipoCliente(f["tipo"])
            try:
                c = gc.nuovo(
                    tipo=tipo,
                    nome=f.get("nome", ""),
                    cognome=f.get("cognome", ""),
                    ragione_sociale=f.get("ragione_sociale", ""),
                    codice_fiscale=f.get("codice_fiscale", "").upper(),
                    partita_iva=f.get("partita_iva", ""),
                    forma_giuridica=f.get("forma_giuridica", ""),
                    data_nascita=f.get("data_nascita", ""),
                    luogo_nascita=f.get("luogo_nascita", ""),
                    provincia_nascita=f.get("provincia_nascita", ""),
                    sesso=f.get("sesso", ""),
                    nazionalita=f.get("nazionalita", "Italiana"),
                    rappresentante_legale=f.get("rappresentante_legale", ""),
                    cf_rappresentante=f.get("cf_rappresentante", "").upper(),
                    avvocato_referente=f.get("avvocato_referente", ""),
                    provenienza=f.get("provenienza", ""),
                    note=f.get("note", ""),
                )
                # indirizzi e recapiti
                _salva_indirizzo(gc, c.id, "residenza", f)
                _salva_indirizzo(gc, c.id, "domicilio", f, prefix="dom_")
                _salva_indirizzo(gc, c.id, "sede_legale", f, prefix="sl_")
                gc.aggiorna_recapiti(c.id,
                    telefono=f.get("telefono", ""),
                    cellulare=f.get("cellulare", ""),
                    email=f.get("email", ""),
                    pec=f.get("pec", ""),
                    fax=f.get("fax", ""),
                    sito_web=f.get("sito_web", ""),
                )
                flash(f"Cliente '{c.nome_completo}' aggiunto.", "success")
                return redirect(url_for("dettaglio_cliente", id_cliente=c.id))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        return render_template(
            "clienti/form.html",
            cliente=None,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumento),
            tribunali=reginde.elenca_uffici(),
        )

    @app.route("/clienti/<id_cliente>")
    def dettaglio_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))
        agenda = get_agenda()
        apps_cliente = agenda.cerca(cliente=c.nome_completo)
        return render_template("clienti/dettaglio.html", cliente=c, apps_cliente=apps_cliente)

    @app.route("/clienti/<id_cliente>/modifica", methods=["GET", "POST"])
    def modifica_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            flash("Cliente non trovato.", "warning")
            return redirect(url_for("lista_clienti"))

        if request.method == "POST":
            f = request.form
            try:
                gc.aggiorna(id_cliente,
                    nome=f.get("nome", c.nome),
                    cognome=f.get("cognome", c.cognome),
                    ragione_sociale=f.get("ragione_sociale", c.ragione_sociale),
                    codice_fiscale=f.get("codice_fiscale", c.codice_fiscale).upper(),
                    partita_iva=f.get("partita_iva", c.partita_iva),
                    forma_giuridica=f.get("forma_giuridica", c.forma_giuridica),
                    data_nascita=f.get("data_nascita", c.data_nascita),
                    luogo_nascita=f.get("luogo_nascita", c.luogo_nascita),
                    provincia_nascita=f.get("provincia_nascita", c.provincia_nascita),
                    sesso=f.get("sesso", c.sesso),
                    nazionalita=f.get("nazionalita", c.nazionalita),
                    rappresentante_legale=f.get("rappresentante_legale", c.rappresentante_legale),
                    cf_rappresentante=f.get("cf_rappresentante", c.cf_rappresentante).upper(),
                    avvocato_referente=f.get("avvocato_referente", c.avvocato_referente),
                    provenienza=f.get("provenienza", c.provenienza),
                    note=f.get("note", c.note),
                    stato=StatoCliente(f.get("stato", c.stato.value)),
                )
                _salva_indirizzo(gc, id_cliente, "residenza", f)
                _salva_indirizzo(gc, id_cliente, "domicilio", f, prefix="dom_")
                _salva_indirizzo(gc, id_cliente, "sede_legale", f, prefix="sl_")
                gc.aggiorna_recapiti(id_cliente,
                    telefono=f.get("telefono", ""),
                    cellulare=f.get("cellulare", ""),
                    email=f.get("email", ""),
                    pec=f.get("pec", ""),
                    fax=f.get("fax", ""),
                    sito_web=f.get("sito_web", ""),
                )
                gc.aggiorna_documento(id_cliente,
                    tipo=TipoDocumento(f.get("doc_tipo", c.documento.tipo.value)),
                    numero=f.get("doc_numero", ""),
                    rilasciato_da=f.get("doc_rilasciato_da", ""),
                    data_rilascio=f.get("doc_data_rilascio", ""),
                    data_scadenza=f.get("doc_data_scadenza", ""),
                )
                flash("Cliente aggiornato.", "success")
                return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))
            except (ValueError, KeyError) as e:
                flash(str(e), "danger")

        reginde = ClientReGINde()
        return render_template(
            "clienti/form.html",
            cliente=c,
            tipi=list(TipoCliente),
            stati=list(StatoCliente),
            tipi_doc=list(TipoDocumento),
            tribunali=reginde.elenca_uffici(),
        )

    @app.route("/clienti/<id_cliente>/elimina", methods=["POST"])
    def elimina_cliente(id_cliente):
        gc = get_clienti()
        try:
            gc.elimina(id_cliente)
            flash("Cliente eliminato.", "success")
        except KeyError as e:
            flash(str(e), "danger")
        return redirect(url_for("lista_clienti"))

    @app.route("/clienti/<id_cliente>/procedimento", methods=["POST"])
    def aggiungi_procedimento(id_cliente):
        gc = get_clienti()
        f = request.form
        try:
            proc = RiferimentoProcedimento(
                numero_rg=f["numero_rg"],
                anno=int(f.get("anno", datetime.now().year)),
                tribunale=f.get("tribunale", ""),
                descrizione=f.get("descrizione", ""),
                data_apertura=f.get("data_apertura", date.today().isoformat()),
            )
            gc.aggiungi_procedimento(id_cliente, proc)
            flash("Procedimento aggiunto.", "success")
        except (ValueError, KeyError) as e:
            flash(str(e), "danger")
        return redirect(url_for("dettaglio_cliente", id_cliente=id_cliente))

    # ---- API clienti

    @app.route("/api/clienti")
    def api_clienti():
        gc = get_clienti()
        q = request.args.get("q", "")
        clienti = gc.cerca(testo=q) if q else gc.tutti()
        return jsonify([c.to_dict() for c in clienti])

    @app.route("/api/clienti/<id_cliente>")
    def api_cliente(id_cliente):
        gc = get_clienti()
        c = gc.get(id_cliente)
        if not c:
            return jsonify({"errore": "Non trovato"}), 404
        return jsonify(c.to_dict())

    @app.route("/api/clienti/statistiche")
    def api_clienti_statistiche():
        return jsonify(get_clienti().statistiche())

    # ---------------------------------------------------------------- helpers

    def _salva_indirizzo(gc, id_c, tipo, f, prefix=""):
        gc.aggiorna_indirizzo(id_c, tipo,
            via=f.get(f"{prefix}via", ""),
            civico=f.get(f"{prefix}civico", ""),
            cap=f.get(f"{prefix}cap", ""),
            comune=f.get(f"{prefix}comune", ""),
            provincia=f.get(f"{prefix}provincia", ""),
            nazione=f.get(f"{prefix}nazione", "Italia"),
        )

    return app
