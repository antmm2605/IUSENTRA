"""Auxiliary deposito routes kept out of the main bootstrap."""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, g, jsonify, request
from web.blueprints.react_shell import render_react_shell_response


def register_deposito_aux_routes(
    app: Flask,
    *,
    get_fascicoli: Callable[[], object],
    run_deposito_validation: Callable[..., object],
) -> None:
    """Register static guides and validation endpoint for deposito telematico."""

    @app.route("/deposito/checklist")
    def deposito_checklist():
        """Checklist operativa per il deposito telematico."""
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("deposito/checklist")

    @app.route("/guida/firma-digitale")
    def guida_firma_digitale():
        """Guida interattiva per la firma digitale."""
        # Pagina React (TelematicoSurfacePage/TelematicoPage): la vista Jinja è stata tolta.
        return render_react_shell_response("guida/firma-digitale")

    @app.route("/api/fascicoli/<id_fasc>/deposito/valida", methods=["POST"])
    def api_deposito_valida(id_fasc):
        try:
            gestore_fascicoli = get_fascicoli()
            fascicolo = gestore_fascicoli.get(id_fasc)
            if not fascicolo:
                return jsonify({"ok": False, "errore": "Fascicolo non trovato."}), 200
            utente = getattr(g, "utente_corrente", None)
            run = run_deposito_validation(
                fasc=fascicolo,
                gf=gestore_fascicoli,
                form_like=request.form,
                operatore=utente.username if utente else "",
            )
            return jsonify({"ok": True, "validation": run.to_dict()}), 200
        except Exception as exc:
            app.logger.exception("Errore api_deposito_valida: %s", exc)
            return jsonify({"ok": False, "errore": "Validazione deposito non completata. Verifica i dati e riprova."}), 200
