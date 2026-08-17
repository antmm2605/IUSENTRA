from __future__ import annotations

from datetime import date
from functools import wraps

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from pct.strumenti_legali import GestioneStrumentiLegali
from web.helpers import get_clienti, get_fascicoli

strumenti_legali = Blueprint("strumenti_legali", __name__, url_prefix="/strumenti-legali")

TOOL_METHODS = {
    "uffici_competenti": "ricerca_uffici_competenti",
    "contributo_unificato": "calcola_contributo_unificato",
    "interessi": "calcola_interessi",
    "nota_credito": "genera_nota_precisazione_credito",
    "pignoramento": "simula_pignoramento",
    "ctu": "calcola_ctu",
    "rivalutazione_istat": "calcola_rivalutazione_istat",
    "canone_locazione": "calcola_adeguamento_canone",
    "usura": "verifica_soglia_usura",
    "contributi_cassa_forense": "calcola_contributi_cassa_forense",
    "tfr": "calcola_tfr",
    "onorari_forensi": "calcola_onorari_forensi",
    "custodia_cautelare": "calcola_custodia_cautelare",
    "prescrizione_penale": "calcola_prescrizione_penale",
    "successione_legittima": "calcola_successione_legittima",
    "cedolare_secca": "calcola_cedolare_secca",
    "indennita_licenziamento": "calcola_indennita_licenziamento",
    "piano_ammortamento": "calcola_piano_ammortamento",
    "prescrizione": "calcola_prescrizione",
    "danno_biologico": "calcola_danno_biologico",
    "imposta_registro": "calcola_imposta_registro",
    "interessi_acconti": "calcola_interessi_acconti",
    "maggior_danno": "calcola_maggior_danno",
    "crediti_lavoro": "calcola_crediti_lavoro",
    "danno_parentale": "calcola_danno_parentale",
    "usufrutto": "calcola_usufrutto",
    "quote_riserva": "calcola_quote_riserva",
    "assegno_mantenimento": "stima_assegno_mantenimento",
    "pena_riti_alternativi": "calcola_pena_riti_alternativi",
    "indennita_mediazione": "calcola_indennita_mediazione",
    "patrocinio_spese_stato": "verifica_patrocinio_spese_stato",
    "competenza_valore": "calcola_competenza_valore",
    "termini_processuali": "calcola_termini_processuali",
    "impugnazioni": "calcola_impugnazioni",
    "ravvedimento_operoso": "calcola_ravvedimento_operoso",
    "compenso_a_tempo": "calcola_compenso_a_tempo",
    "conta_giorni": "calcola_conta_giorni",
    "scorporo_iva": "calcola_scorporo_iva",
    "percentuali": "calcola_percentuali",
    "codice_fiscale": "calcola_codice_fiscale",
    "tabella_istat": "tabella_variazioni_istat",
    "tabella_tassi": "tabella_tassi_interesse",
    "taeg": "calcola_taeg",
    "surroga": "calcola_surroga",
    "rivalutazione_media": "calcola_rivalutazione_media",
    "rendimento_bot": "calcola_rendimento_bot",
    "pronti_contro_termine": "calcola_pronti_contro_termine",
    "grado_parentela": "calcola_grado_parentela",
    "reversibilita": "calcola_reversibilita",
    "imposte_successione": "calcola_imposte_successione",
    "valore_catastale": "calcola_valore_catastale",
    "imu": "calcola_imu",
    "imposte_compravendita": "calcola_imposte_compravendita",
    "riparto_spese": "calcola_riparto_spese",
    "categorie_catastali": "tabella_categorie_catastali",
    "irpef": "calcola_irpef_lorda",
    "acconto_imposte": "calcola_acconto_imposte",
    "rateazione_imposte": "calcola_rateazione_imposte",
    "detrazioni_familiari": "calcola_detrazioni_familiari",
    "detrazioni_reddito": "calcola_detrazioni_reddito",
    "detrazione_canone": "calcola_detrazione_canone",
    "regime_forfettario": "calcola_regime_forfettario",
    "fattura_agente": "calcola_fattura_agente",
    "prestazione_occasionale": "calcola_prestazione_occasionale",
}


def _richiedi_login(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)

    return wrapper


def _studio_context() -> dict:
    return {
        "nome": current_app.config.get("STUDIO_NOME", "IUSENTRA"),
        "avvocato": current_app.config.get("STUDIO_AVVOCATO", ""),
        "cf": current_app.config.get("STUDIO_CF", ""),
        "piva": current_app.config.get("STUDIO_PIVA", ""),
        "indirizzo": current_app.config.get("STUDIO_INDIRIZZO", ""),
        "pec": current_app.config.get("SMTP_FROM", ""),
        "fax": current_app.config.get("STUDIO_FAX", ""),
        "luogo": current_app.config.get("STUDIO_LUOGO", ""),
    }


def _gestore_strumenti() -> GestioneStrumentiLegali:
    return GestioneStrumentiLegali(
        normative_db_path=current_app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
    )


def _resolve_context():
    fascicoli = sorted(get_fascicoli().tutti(archiviati=True), key=lambda f: ((f.data_apertura or ""), f.numero), reverse=True)
    clienti_map = {c.id: c for c in get_clienti().tutti()}
    id_fascicolo = request.values.get("id_fascicolo", "").strip()
    fascicolo_sel = get_fascicoli().get(id_fascicolo) if id_fascicolo else None
    cliente_sel = clienti_map.get(fascicolo_sel.id_cliente) if fascicolo_sel and fascicolo_sel.id_cliente else None
    return fascicoli, clienti_map, fascicolo_sel, cliente_sel


def _json_result(fn_name: str):
    gestore = _gestore_strumenti()
    payload = request.get_json(silent=True) if request.is_json else request.form
    try:
        fn = getattr(gestore, fn_name)
        return jsonify({"ok": True, "result": fn(payload)})
    except Exception as exc:
        current_app.logger.exception("Errore strumenti_legali.%s: %s", fn_name, exc)
        return jsonify({"ok": False, "errore": str(exc)}), 200


@strumenti_legali.route("/", methods=["GET", "POST"])
@_richiedi_login
def index():
    gestore = _gestore_strumenti()
    fascicoli, clienti_map, fascicolo_sel, cliente_sel = _resolve_context()
    studio = _studio_context()
    prefill = gestore.build_prefill(
        fascicolo=fascicolo_sel,
        cliente=cliente_sel,
        studio=studio,
        utente=g.get("utente_corrente"),
    )
    form_state = gestore.build_form_state(prefill, request.form if request.method == "POST" else None)
    active_tool = request.values.get("tool", "").strip() or "contributo_unificato"
    results = {}
    onorari_options = gestore.opzioni_onorari_forensi()
    selected_onorari_fasi = (
        request.form.getlist("onorari_fasi")
        if request.method == "POST" and active_tool == "onorari_forensi"
        else ["STUDIO", "INTRODUTTIVA", "ISTRUTTORIA", "DECISIONALE"]
    )

    if request.method == "POST":
        try:
            fn_name = TOOL_METHODS.get(active_tool)
            if fn_name:
                results[active_tool] = getattr(gestore, fn_name)(request.form)
            else:
                flash("Strumento richiesto non riconosciuto.", "warning")
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception as exc:
            current_app.logger.exception("Errore strumenti_legali.index: %s", exc)
            flash(f"Errore durante il calcolo: {exc}", "danger")

    return render_template(
        "strumenti_legali/index.html",
        oggi=date.today(),
        fascicoli=fascicoli,
        clienti_map=clienti_map,
        fascicolo_sel=fascicolo_sel,
        cliente_sel=cliente_sel,
        studio=studio,
        prefill=prefill,
        form_state=form_state,
        active_tool=active_tool,
        results=results,
        moduli=gestore.catalogo_moduli(),
        opzioni_cu=gestore.opzioni_contributo_unificato(),
        opzioni_cu_valore=gestore.opzioni_valore_contributo_unificato(),
        opzioni_pena=gestore.opzioni_pena_riti_alternativi(),
        opzioni_termini=gestore.opzioni_termini_processuali(),
        onorari_options=onorari_options,
        selected_onorari_fasi=selected_onorari_fasi,
    )


@strumenti_legali.route("/api/prefill/<id_fascicolo>", methods=["GET"])
@_richiedi_login
def api_prefill(id_fascicolo: str):
    try:
        fascicolo = get_fascicoli().get(id_fascicolo)
        if not fascicolo:
            return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200
        cliente = get_clienti().get(fascicolo.id_cliente) if fascicolo.id_cliente else None
        prefill = _gestore_strumenti().build_prefill(
            fascicolo=fascicolo,
            cliente=cliente,
            studio=_studio_context(),
            utente=g.get("utente_corrente"),
        )
        return jsonify({"ok": True, "prefill": prefill})
    except Exception as exc:
        current_app.logger.exception("Errore strumenti_legali.api_prefill: %s", exc)
        return jsonify({"ok": False, "errore": str(exc)}), 200


@strumenti_legali.route("/api/contributo-unificato", methods=["POST"])
@_richiedi_login
def api_contributo_unificato():
    return _json_result("calcola_contributo_unificato")


@strumenti_legali.route("/api/interessi", methods=["POST"])
@_richiedi_login
def api_interessi():
    return _json_result("calcola_interessi")


@strumenti_legali.route("/api/nota-credito", methods=["POST"])
@_richiedi_login
def api_nota_credito():
    return _json_result("genera_nota_precisazione_credito")


@strumenti_legali.route("/api/pignoramento", methods=["POST"])
@_richiedi_login
def api_pignoramento():
    return _json_result("simula_pignoramento")


@strumenti_legali.route("/api/ctu", methods=["POST"])
@_richiedi_login
def api_ctu():
    return _json_result("calcola_ctu")


@strumenti_legali.route("/api/rivalutazione-istat", methods=["POST"])
@_richiedi_login
def api_rivalutazione_istat():
    return _json_result("calcola_rivalutazione_istat")


@strumenti_legali.route("/api/canone-locazione", methods=["POST"])
@_richiedi_login
def api_canone_locazione():
    return _json_result("calcola_adeguamento_canone")


@strumenti_legali.route("/api/usura", methods=["POST"])
@_richiedi_login
def api_usura():
    return _json_result("verifica_soglia_usura")


@strumenti_legali.route("/api/contributi-cassa-forense", methods=["POST"])
@_richiedi_login
def api_contributi_cassa_forense():
    return _json_result("calcola_contributi_cassa_forense")


@strumenti_legali.route("/api/tfr", methods=["POST"])
@_richiedi_login
def api_tfr():
    return _json_result("calcola_tfr")


@strumenti_legali.route("/api/onorari-forensi", methods=["POST"])
@_richiedi_login
def api_onorari_forensi():
    return _json_result("calcola_onorari_forensi")


@strumenti_legali.route("/api/indennita-mediazione", methods=["POST"])
@_richiedi_login
def api_indennita_mediazione():
    return _json_result("calcola_indennita_mediazione")


@strumenti_legali.route("/api/pena-riti-alternativi", methods=["POST"])
@_richiedi_login
def api_pena_riti_alternativi():
    return _json_result("calcola_pena_riti_alternativi")


@strumenti_legali.route("/api/custodia-cautelare", methods=["POST"])
@_richiedi_login
def api_custodia_cautelare():
    return _json_result("calcola_custodia_cautelare")


@strumenti_legali.route("/api/prescrizione-penale", methods=["POST"])
@_richiedi_login
def api_prescrizione_penale():
    return _json_result("calcola_prescrizione_penale")


@strumenti_legali.route("/api/successione-legittima", methods=["POST"])
@_richiedi_login
def api_successione_legittima():
    return _json_result("calcola_successione_legittima")


@strumenti_legali.route("/api/cedolare-secca", methods=["POST"])
@_richiedi_login
def api_cedolare_secca():
    return _json_result("calcola_cedolare_secca")


@strumenti_legali.route("/api/indennita-licenziamento", methods=["POST"])
@_richiedi_login
def api_indennita_licenziamento():
    return _json_result("calcola_indennita_licenziamento")


@strumenti_legali.route("/api/piano-ammortamento", methods=["POST"])
@_richiedi_login
def api_piano_ammortamento():
    return _json_result("calcola_piano_ammortamento")


@strumenti_legali.route("/api/istat-categorie", methods=["GET"])
@_richiedi_login
def api_istat_categorie():
    """Restituisce l'ultimo mese ISTAT disponibile per FOI e NIC."""
    try:
        from pct.normative_tables import GestioneTabelleNormative
        nt = GestioneTabelleNormative(
            db_path=current_app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
        )
        return jsonify({
            "ok": True,
            "foi_last": nt.istat_last_available("foi"),
            "nic_last": nt.istat_last_available("nic"),
        })
    except Exception as exc:
        return jsonify({"ok": False, "errore": str(exc)}), 200


@strumenti_legali.route("/api/prescrizione", methods=["POST"])
@_richiedi_login
def api_prescrizione():
    return _json_result("calcola_prescrizione")


@strumenti_legali.route("/api/danno-biologico", methods=["POST"])
@_richiedi_login
def api_danno_biologico():
    return _json_result("calcola_danno_biologico")


@strumenti_legali.route("/api/imposta-registro", methods=["POST"])
@_richiedi_login
def api_imposta_registro():
    return _json_result("calcola_imposta_registro")


@strumenti_legali.route("/api/interessi-acconti", methods=["POST"])
@_richiedi_login
def api_interessi_acconti():
    return _json_result("calcola_interessi_acconti")


@strumenti_legali.route("/api/maggior-danno", methods=["POST"])
@_richiedi_login
def api_maggior_danno():
    return _json_result("calcola_maggior_danno")


@strumenti_legali.route("/api/danno-parentale", methods=["POST"])
@_richiedi_login
def api_danno_parentale():
    return _json_result("calcola_danno_parentale")


@strumenti_legali.route("/api/usufrutto", methods=["POST"])
@_richiedi_login
def api_usufrutto():
    return _json_result("calcola_usufrutto")


@strumenti_legali.route("/api/quote-riserva", methods=["POST"])
@_richiedi_login
def api_quote_riserva():
    return _json_result("calcola_quote_riserva")


@strumenti_legali.route("/api/assegno-mantenimento", methods=["POST"])
@_richiedi_login
def api_assegno_mantenimento():
    return _json_result("stima_assegno_mantenimento")


@strumenti_legali.route("/api/patrocinio-spese-stato", methods=["POST"])
@_richiedi_login
def api_patrocinio_spese_stato():
    return _json_result("verifica_patrocinio_spese_stato")


@strumenti_legali.route("/api/competenza-valore", methods=["POST"])
@_richiedi_login
def api_competenza_valore():
    return _json_result("calcola_competenza_valore")


@strumenti_legali.route("/api/termini-processuali", methods=["POST"])
@_richiedi_login
def api_termini_processuali():
    return _json_result("calcola_termini_processuali")


@strumenti_legali.route("/api/impugnazioni", methods=["POST"])
@_richiedi_login
def api_impugnazioni():
    return _json_result("calcola_impugnazioni")


@strumenti_legali.route("/api/ravvedimento-operoso", methods=["POST"])
@_richiedi_login
def api_ravvedimento_operoso():
    return _json_result("calcola_ravvedimento_operoso")


@strumenti_legali.route("/api/compenso-a-tempo", methods=["POST"])
@_richiedi_login
def api_compenso_a_tempo():
    return _json_result("calcola_compenso_a_tempo")


@strumenti_legali.route("/api/conta-giorni", methods=["POST"])
@_richiedi_login
def api_conta_giorni():
    return _json_result("calcola_conta_giorni")


@strumenti_legali.route("/api/scorporo-iva", methods=["POST"])
@_richiedi_login
def api_scorporo_iva():
    return _json_result("calcola_scorporo_iva")


@strumenti_legali.route("/api/percentuali", methods=["POST"])
@_richiedi_login
def api_percentuali():
    return _json_result("calcola_percentuali")


@strumenti_legali.route("/api/codice-fiscale", methods=["POST"])
@_richiedi_login
def api_codice_fiscale():
    return _json_result("calcola_codice_fiscale")


@strumenti_legali.route("/api/tabella-istat", methods=["POST"])
@_richiedi_login
def api_tabella_istat():
    return _json_result("tabella_variazioni_istat")


@strumenti_legali.route("/api/tabella-tassi", methods=["POST"])
@_richiedi_login
def api_tabella_tassi():
    return _json_result("tabella_tassi_interesse")


@strumenti_legali.route("/api/taeg", methods=["POST"])
@_richiedi_login
def api_taeg():
    return _json_result("calcola_taeg")


@strumenti_legali.route("/api/surroga", methods=["POST"])
@_richiedi_login
def api_surroga():
    return _json_result("calcola_surroga")


@strumenti_legali.route("/api/rivalutazione-media", methods=["POST"])
@_richiedi_login
def api_rivalutazione_media():
    return _json_result("calcola_rivalutazione_media")


@strumenti_legali.route("/api/rendimento-bot", methods=["POST"])
@_richiedi_login
def api_rendimento_bot():
    return _json_result("calcola_rendimento_bot")


@strumenti_legali.route("/api/pronti-contro-termine", methods=["POST"])
@_richiedi_login
def api_pronti_contro_termine():
    return _json_result("calcola_pronti_contro_termine")


@strumenti_legali.route("/api/grado-parentela", methods=["POST"])
@_richiedi_login
def api_grado_parentela():
    return _json_result("calcola_grado_parentela")


@strumenti_legali.route("/api/reversibilita", methods=["POST"])
@_richiedi_login
def api_reversibilita():
    return _json_result("calcola_reversibilita")


@strumenti_legali.route("/api/imposte-successione", methods=["POST"])
@_richiedi_login
def api_imposte_successione():
    return _json_result("calcola_imposte_successione")


@strumenti_legali.route("/api/valore-catastale", methods=["POST"])
@_richiedi_login
def api_valore_catastale():
    return _json_result("calcola_valore_catastale")


@strumenti_legali.route("/api/imu", methods=["POST"])
@_richiedi_login
def api_imu():
    return _json_result("calcola_imu")


@strumenti_legali.route("/api/imposte-compravendita", methods=["POST"])
@_richiedi_login
def api_imposte_compravendita():
    return _json_result("calcola_imposte_compravendita")


@strumenti_legali.route("/api/riparto-spese", methods=["POST"])
@_richiedi_login
def api_riparto_spese():
    return _json_result("calcola_riparto_spese")


@strumenti_legali.route("/api/categorie-catastali", methods=["POST"])
@_richiedi_login
def api_categorie_catastali():
    return _json_result("tabella_categorie_catastali")


@strumenti_legali.route("/api/irpef", methods=["POST"])
@_richiedi_login
def api_irpef():
    return _json_result("calcola_irpef_lorda")


@strumenti_legali.route("/api/acconto-imposte", methods=["POST"])
@_richiedi_login
def api_acconto_imposte():
    return _json_result("calcola_acconto_imposte")


@strumenti_legali.route("/api/rateazione-imposte", methods=["POST"])
@_richiedi_login
def api_rateazione_imposte():
    return _json_result("calcola_rateazione_imposte")


@strumenti_legali.route("/api/detrazioni-familiari", methods=["POST"])
@_richiedi_login
def api_detrazioni_familiari():
    return _json_result("calcola_detrazioni_familiari")


@strumenti_legali.route("/api/detrazioni-reddito", methods=["POST"])
@_richiedi_login
def api_detrazioni_reddito():
    return _json_result("calcola_detrazioni_reddito")


@strumenti_legali.route("/api/detrazione-canone", methods=["POST"])
@_richiedi_login
def api_detrazione_canone():
    return _json_result("calcola_detrazione_canone")


@strumenti_legali.route("/api/regime-forfettario", methods=["POST"])
@_richiedi_login
def api_regime_forfettario():
    return _json_result("calcola_regime_forfettario")


@strumenti_legali.route("/api/fattura-agente", methods=["POST"])
@_richiedi_login
def api_fattura_agente():
    return _json_result("calcola_fattura_agente")


@strumenti_legali.route("/api/prestazione-occasionale", methods=["POST"])
@_richiedi_login
def api_prestazione_occasionale():
    return _json_result("calcola_prestazione_occasionale")


@strumenti_legali.route("/api/usura-categorie", methods=["GET"])
@_richiedi_login
def api_usura_categorie():
    """Elenco categorie di credito con soglie usura correnti."""
    try:
        from pct.normative_tables import GestioneTabelleNormative
        nt = GestioneTabelleNormative(
            db_path=current_app.config.get("NORMATIVE_TABLES_DB", "./intelligence/tabelle_normative.json")
        )
        return jsonify({"ok": True, "categorie": nt.usura_categorie()})
    except Exception as exc:
        return jsonify({"ok": False, "errore": str(exc)}), 200
