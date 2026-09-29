"""Rotte della contabilità di studio: riepilogo annuale per cassa e registro delle fatture emesse.

Solo lettura (permesso ``fatturazione.leggi``). Logica in ``pct.contabilita``; base normativa nei moduli.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request


def _anno(valore: Any) -> int:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        return int(str(valore or "").strip())
    except ValueError:
        return datetime.now(ZoneInfo("Europe/Rome")).year


def register_contabilita_routes(app: Flask, core: dict[str, Any]) -> None:
    get_prima_nota = core["get_prima_nota"]
    get_fatturazione = core["get_fatturazione"]
    get_config_studio = core["get_config_studio"]
    audit = core["audit"]

    def _puo_leggere() -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso("fatturazione.leggi"))
        except Exception:
            return False

    def _regime() -> str:
        try:
            return str(get_config_studio().config.fatturazione.regime_fiscale or "RF01")
        except Exception:
            return "RF01"

    @app.route("/api/v1/ui/prima-nota/riepilogo")
    def contabilita_riepilogo():
        from pct.contabilita.registro_iva import registro_fatture_emesse
        from pct.contabilita.riepilogo import riepilogo_annuale

        if not _puo_leggere():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        anno = _anno(request.args.get("anno"))
        regime = _regime()
        try:
            esito = riepilogo_annuale(get_prima_nota(), anno, regime=regime,
                                      startup=str(request.args.get("startup") or "") == "1")
            if regime != "RF19":
                registro = registro_fatture_emesse(get_fatturazione(), anno,
                                                   periodicita=str(request.args.get("periodicita") or "trimestrale"))
                esito["registro_iva"] = {k: registro[k] for k in ("liquidazioni", "proforma_escluse", "totale_imponibile",
                                                                  "totale_iva", "note")}
                esito["registro_iva"]["fatture"] = len(registro["fatture"])
            return jsonify({"ok": True, **esito})
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        except Exception as exc:
            app.logger.exception("Errore riepilogo contabile: %s", exc)
            return jsonify({"ok": False, "message": "Riepilogo non disponibile."}), 200

    @app.route("/prima-nota/registro-iva.csv")
    def contabilita_registro_iva_csv():
        from pct.contabilita.registro_iva import csv_registro, registro_fatture_emesse

        if not _puo_leggere():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        anno = _anno(request.args.get("anno"))
        registro = registro_fatture_emesse(get_fatturazione(), anno,
                                           periodicita=str(request.args.get("periodicita") or "trimestrale"))
        audit("contabilita.registro_iva_export", "prima_nota", str(anno), dettagli="registro fatture emesse")
        return Response(csv_registro(registro), mimetype="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=registro-fatture-emesse-{anno}.csv"})
