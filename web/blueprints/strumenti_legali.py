from __future__ import annotations

from functools import wraps

from flask import Blueprint, current_app, g, jsonify, redirect, request, url_for

from pct.calcolatori.metodi import TOOL_METHODS  # noqa: F401  (fonte unica nel dominio, usata anche da Lex)
from pct.strumenti_legali import GestioneStrumentiLegali
from web.helpers import get_clienti, get_fascicoli

strumenti_legali = Blueprint("strumenti_legali", __name__, url_prefix="/strumenti-legali")


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
    """La pagina è solo React (richiesta dell'avvocato del 31/10/2026): niente più vista Jinja.

    Anche le finestre storiche con ``_legacy`` o un vecchio modulo inviato in POST ricevono la pagina
    React; i calcoli passano dalle API ``/strumenti-legali/api/*`` e da ``/api/v1/ui/strumenti-legali``.
    """
    from web.blueprints.react_shell import render_react_shell_response

    if request.method == "POST":
        parametri = {k: v for k, v in request.values.items() if k in {"tool", "id_fascicolo"} and v}
        return redirect(url_for("strumenti_legali.index", **parametri), code=303)
    return render_react_shell_response("strumenti-legali")


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
