from __future__ import annotations

from datetime import date
from functools import wraps

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from pct.strumenti_legali import GestioneStrumentiLegali
from web.helpers import get_clienti, get_fascicoli
from web.blueprints.react_shell import render_react_shell_response

strumenti_legali = Blueprint("strumenti_legali", __name__, url_prefix="/strumenti-legali")

TOOL_METHODS = {
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


def _richiede_vista_classica() -> bool:
    return request.args.get("_legacy") == "1"


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
    if request.method == "GET" and not _richiede_vista_classica():
        return render_react_shell_response("strumenti-legali")
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
