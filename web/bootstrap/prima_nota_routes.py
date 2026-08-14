"""Route della prima nota di studio (registro cronologico di cassa).

Shell React su /prima-nota; scritture con audit. Il registro non si riscrive:
le correzioni passano dallo storno motivato.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from web.blueprints.react_shell import render_react_shell_response


def register_prima_nota_routes(app: Flask, core: dict[str, Any]) -> None:
    get_prima_nota = core["get_prima_nota"]
    get_fatturazione = core["get_fatturazione"]
    audit = core["audit"]

    def _permesso(scrittura: bool = False) -> bool:
        utente = g.get("utente_corrente")
        chiave = "fatturazione.scrivi" if scrittura else "fatturazione.leggi"
        try:
            return bool(utente and utente.ha_permesso(chiave))
        except Exception:
            return False

    @app.route("/prima-nota")
    def prima_nota_page():
        return render_react_shell_response("prima-nota")

    @app.route("/api/v1/ui/prima-nota")
    def prima_nota_payload():
        from web.services.react_prima_nota_bridge import build_react_prima_nota_payload

        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            return jsonify(
                build_react_prima_nota_payload(get_prima_nota=get_prima_nota, query=request.args)
            )
        except Exception as exc:
            app.logger.exception("Errore payload prima nota: %s", exc)
            return jsonify({"ok": False, "message": "Prima nota non disponibile."}), 200

    @app.route("/prima-nota/registra", methods=["POST"])
    def prima_nota_registra():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        utente = g.get("utente_corrente")
        try:
            movimento = get_prima_nota().registra(
                data=str(dati.get("data") or ""),
                tipo=str(dati.get("tipo") or ""),
                importo=dati.get("importo"),
                categoria=str(dati.get("categoria") or ""),
                controparte=str(dati.get("controparte") or ""),
                causale=str(dati.get("causale") or ""),
                metodo=str(dati.get("metodo") or "banca"),
                fascicolo_id=str(dati.get("fascicoloId") or ""),
                documento_riferimento=str(dati.get("documento") or ""),
                creato_da=getattr(utente, "username", "") or "",
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("prima_nota.registrato", "prima_nota", movimento.id, dettagli=f"{movimento.tipo} {movimento.importo}")
        message = f"Movimento registrato: {movimento.tipo.lower()} di {movimento.importo:.2f} EUR."
        return jsonify({"ok": True, "message": message, "messaggio": message, "movimentoId": movimento.id})

    @app.route("/prima-nota/<movimento_id>/storna", methods=["POST"])
    def prima_nota_storna(movimento_id: str):
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        utente = g.get("utente_corrente")
        try:
            storno = get_prima_nota().storna(
                movimento_id,
                motivo=str(dati.get("motivo") or ""),
                attore=getattr(utente, "username", "") or "",
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("prima_nota.stornato", "prima_nota", movimento_id, dettagli=storno.causale)
        return jsonify({"ok": True, "message": "Storno registrato: il movimento originale resta a registro."})

    @app.route("/prima-nota/riconcilia-parcelle", methods=["POST"])
    def prima_nota_riconcilia():
        if not _permesso(scrittura=True):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        utente = g.get("utente_corrente")
        try:
            creati = get_prima_nota().incassi_da_parcelle(
                get_fatturazione(), attore=getattr(utente, "username", "") or ""
            )
        except Exception as exc:
            app.logger.exception("Errore riconciliazione prima nota: %s", exc)
            return jsonify({"ok": False, "message": f"Riconciliazione non riuscita: {exc}"}), 200
        audit("prima_nota.riconciliazione", "prima_nota", "parcelle", dettagli=f"{len(creati)} incassi")
        message = (
            f"{len(creati)} incassi importati dalle parcelle pagate."
            if creati
            else "Nessuna parcella pagata da importare: registro gia' allineato."
        )
        return jsonify({"ok": True, "message": message, "messaggio": message, "creati": len(creati)})

    @app.route("/prima-nota/esporta.csv")
    def prima_nota_esporta():
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        csv_text = get_prima_nota().esporta_csv(
            dal=str(request.args.get("dal") or ""),
            al=str(request.args.get("al") or ""),
        )
        audit("prima_nota.export", "prima_nota", "csv", dettagli="export commercialista")
        return Response(
            "﻿" + csv_text,
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=prima-nota.csv"},
        )
