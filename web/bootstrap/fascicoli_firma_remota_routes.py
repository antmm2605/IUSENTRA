"""Rotte della firma remota: stato del prestatore, invio del codice OTP, firma del documento.

Base normativa: Reg. eIDAS 910/2014 art. 29 (dispositivo gestito dal prestatore per conto del
firmatario); CAD art. 20; D.M. 44/2011 art. 12. La logica è in web/services/firma_remota_runtime.
"""

from __future__ import annotations

from typing import Any, Callable

from flask import jsonify, request


def register_firma_remota_routes(
    app: Any,
    *,
    dipendenze: Any,
    normalizza_modalita_firma_visibile: Callable[[str], str],
    luogo_timbro_firma_visibile: Callable[[], str],
) -> None:
    from web.services import firma_remota_runtime as runtime
    from web.services.fascicoli_signature_options import nota_con_firma_visibile, normalizza_data_ora_firma_visibile

    @app.route("/api/firma/remota/stato", methods=["GET"])
    def api_firma_remota_stato():
        try:
            return jsonify(runtime.stato(dipendenze))
        except Exception as exc:
            app.logger.exception("Errore api_firma_remota_stato: %s", exc)
            return jsonify({"ok": False, "attiva": False, "messaggio": "Stato della firma remota non disponibile."})

    @app.route("/api/firma/remota/otp", methods=["POST"])
    def api_firma_remota_otp():
        try:
            corpo, stato = runtime.invia_codice(dipendenze, request.get_json(silent=True) or {})
            return jsonify(corpo), stato
        except Exception as exc:
            app.logger.exception("Errore api_firma_remota_otp: %s", exc)
            return jsonify({"ok": False, "messaggio": "Invio del codice non riuscito."}), 500

    @app.route("/api/firma/remota/firma-documento", methods=["POST"])
    def api_firma_remota_documento():
        try:
            dati = request.get_json(silent=True) or {}
            cfg_firma = dipendenze.get_config_studio().config.firma
            modo = normalizza_modalita_firma_visibile(
                str(dati.get("visible_signature_mode") or getattr(cfg_firma, "visible_signature_mode", "laterale")).strip())
            luogo = str(dati.get("visible_signature_place") or luogo_timbro_firma_visibile()).strip()
            modo_data = normalizza_data_ora_firma_visibile(dati.get("visible_signature_datetime_mode"))
            corpo, stato = runtime.firma_documento(
                dipendenze, dati,
                visibile={"visible_signature_mode": modo, "visible_signature_place": luogo,
                          "visible_signature_datetime_mode": modo_data},
                nota=nota_con_firma_visibile("Versione firmata con firma remota", modo, luogo, modo_data),
            )
            return jsonify(corpo), stato
        except Exception as exc:
            app.logger.exception("Errore api_firma_remota_documento: %s", exc)
            return jsonify({"ok": False, "messaggio": "Firma remota non completata: il documento non è stato modificato."}), 500


__all__ = ["register_firma_remota_routes"]
