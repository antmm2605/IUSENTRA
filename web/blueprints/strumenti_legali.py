from __future__ import annotations

from datetime import date
from functools import wraps

from flask import Blueprint, current_app, flash, g, jsonify, redirect, render_template, request, url_for

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
        "nome": current_app.config.get("STUDIO_NOME", "Studio Legale PCT"),
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
    payload = request.get_json(silent=True) or request.form.to_dict()
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

    if request.method == "POST":
        try:
            if active_tool == "contributo_unificato":
                results[active_tool] = gestore.calcola_contributo_unificato(request.form)
            elif active_tool == "interessi":
                results[active_tool] = gestore.calcola_interessi(request.form)
            elif active_tool == "nota_credito":
                results[active_tool] = gestore.genera_nota_precisazione_credito(request.form)
            elif active_tool == "pignoramento":
                results[active_tool] = gestore.simula_pignoramento(request.form)
            elif active_tool == "ctu":
                results[active_tool] = gestore.calcola_ctu(request.form)
            elif active_tool == "rivalutazione_istat":
                results[active_tool] = gestore.calcola_rivalutazione_istat(request.form)
            elif active_tool == "canone_locazione":
                results[active_tool] = gestore.calcola_adeguamento_canone(request.form)
            elif active_tool == "usura":
                results[active_tool] = gestore.verifica_soglia_usura(request.form)
            elif active_tool == "contributi_cassa_forense":
                results[active_tool] = gestore.calcola_contributi_cassa_forense(request.form)
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
