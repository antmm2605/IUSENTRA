"""API JSON dell'agenda legacy e controllo dei permessi delle sue scritture."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from flask import Flask, flash, g, jsonify, redirect, request, url_for

from web.services.request_mode import richiede_json


def agenda_non_autorizzato(permesso: str):
    """Risposta 403 se l'utente corrente non ha il permesso sull'agenda, altrimenti None."""
    utente = getattr(g, "utente_corrente", None)
    if utente is not None and utente.ha_permesso(permesso):
        return None
    messaggio = "Non hai il permesso per modificare l'agenda."
    if richiede_json():
        return jsonify({"ok": False, "message": messaggio}), 403
    flash(messaggio, "danger")
    return redirect(url_for("agenda_view"))


def register_agenda_api_routes(
    app: Flask,
    *,
    get_agenda: Callable[[], object],
    audit: Callable[..., None],
    allinea_spostamento: Callable[[str, str, str], None],
) -> None:
    _allinea_scadenze_spostamento = allinea_spostamento

    @app.route("/api/agenda/<id_app>/sposta", methods=["POST"])
    def api_sposta_appuntamento(id_app):
        if not g.utente_corrente or not g.utente_corrente.ha_permesso("agenda.scrivi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        agenda = get_agenda()
        appt = agenda.get(id_app)
        if not appt:
            return jsonify({"errore": "Appuntamento non trovato"}), 404
        payload = request.get_json(silent=True) or {}
        nuova_data = payload.get("data")
        nuova_data_ora = payload.get("data_ora")
        if nuova_data and not nuova_data_ora:
            ora_orig = appt.data_ora_dt.strftime("%H:%M:%S")
            nuova_data_ora = f"{nuova_data}T{ora_orig}"
        if not nuova_data_ora:
            return jsonify({"errore": "Parametro 'data' o 'data_ora' richiesto"}), 400
        try:
            data_prima = str(appt.data_ora or "")
            appt = agenda.modifica(id_app, data_ora=nuova_data_ora)
            _allinea_scadenze_spostamento(id_app, data_prima, nuova_data_ora)
            audit("agenda.sposta", "appuntamento", id_app, dettagli=f"→ {nuova_data_ora}")
            return jsonify({"ok": True, "data_ora": appt.data_ora})
        except (ValueError, KeyError) as e:
            return jsonify({"errore": str(e)}), 409
    @app.route("/api/agenda")
    def api_agenda():
        try:
            agenda = get_agenda()
            da_str = request.args.get("da")
            a_str = request.args.get("a")
            da = date.fromisoformat(da_str) if da_str else None
            a = date.fromisoformat(a_str) if a_str else None
            apps = agenda.cerca(da=da, a=a)
            return jsonify([a.to_dict() for a in apps])
        except Exception as e:
            app.logger.exception("Errore api_agenda: %s", e)
            return jsonify([])
    @app.route("/api/agenda/<id_app>")
    def api_appuntamento(id_app):
        try:
            agenda = get_agenda()
            appt = agenda.get(id_app)
            if not appt:
                return jsonify({"errore": "Non trovato"}), 404
            return jsonify(appt.to_dict())
        except Exception as e:
            app.logger.exception("Errore api_appuntamento: %s", e)
            return jsonify({"errore": "Appuntamento non disponibile in questo momento."}), 503
    @app.route("/api/reminder")
    def api_reminder():
        try:
            agenda = get_agenda()
            entro = int(request.args.get("entro", 60))
            apps = agenda.prossimi_reminder(entro_minuti=entro)
            return jsonify([a.to_dict() for a in apps])
        except Exception as e:
            app.logger.exception("Errore api_reminder: %s", e)
            return jsonify([])
    @app.route("/api/statistiche")
    def api_statistiche():
        try:
            return jsonify(get_agenda().statistiche())
        except Exception as e:
            app.logger.exception("Errore api_statistiche: %s", e)
            return jsonify({"errore": "Statistiche non disponibili in questo momento."}), 503
