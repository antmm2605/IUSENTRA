"""Route degli incarichi CTU collegati al fascicolo.

Base normativa: artt. 191-201 c.p.c.; art. 195 c.3 c.p.c. (timeline fissata
dall'ordinanza del giudice). La sezione UI vive nel dettaglio fascicolo; le
scadenze proposte nascono in BOZZA nello scadenziario.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, g, jsonify, request

_STATO_LABEL = {
    "NOMINATO": "Nominato",
    "GIURAMENTO": "Giuramento",
    "OPERAZIONI": "Operazioni peritali",
    "BOZZA_TRASMESSA": "Bozza trasmessa",
    "OSSERVAZIONI": "Osservazioni parti",
    "DEPOSITATA": "Relazione depositata",
    "LIQUIDAZIONE": "Liquidazione",
    "CHIUSO": "Chiuso",
}


def _incarico_payload(incarico: Any) -> dict[str, Any]:
    return {
        "id": incarico.id,
        "ruoloStudio": incarico.ruolo_studio,
        "stato": incarico.stato,
        "statoLabel": _STATO_LABEL.get(incarico.stato, incarico.stato),
        "nomeCtu": incarico.nome_ctu,
        "albo": incarico.albo,
        "pecCtu": incarico.pec_ctu,
        "quesiti": incarico.quesiti,
        "timeline": incarico.timeline(),
        "avvisi": incarico.termini_incoerenti(),
        "consulentiParte": [
            {"nome": ctp.nome, "parte": ctp.parte, "email": ctp.email}
            for ctp in incarico.consulenti_parte
        ],
        "actions": {
            "aggiorna": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/aggiorna",
            "proponiScadenze": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/proponi-scadenze",
            "aggiungiCtp": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/ctp",
        },
    }


def register_ctu_routes(app: Flask, core: dict[str, Any]) -> None:
    get_ctu = core["get_ctu"]
    get_scadenziario = core["get_scadenziario"]
    audit = core["audit"]

    def _permesso() -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso("fascicoli.scrivi"))
        except Exception:
            return False

    @app.route("/api/v1/ui/fascicoli/<id_fasc>/ctu")
    def fascicolo_ctu_payload(id_fasc: str):
        utente = g.get("utente_corrente")
        if not utente:
            return jsonify({"ok": False, "message": "Accesso richiesto."}), 403
        try:
            incarichi = get_ctu().per_fascicolo(id_fasc)
            return jsonify({"ok": True, "incarichi": [_incarico_payload(i) for i in incarichi]})
        except Exception as exc:
            app.logger.exception("Errore payload CTU %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "message": "Incarichi CTU non disponibili.", "incarichi": []}), 200

    @app.route("/fascicoli/<id_fasc>/ctu/nuovo", methods=["POST"])
    def fascicolo_ctu_nuovo(id_fasc: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        try:
            incarico = get_ctu().nuovo(
                fascicolo_id=id_fasc,
                ruolo_studio=str(dati.get("ruoloStudio") or dati.get("ruolo_studio") or "PARTE"),
                nome_ctu=str(dati.get("nomeCtu") or dati.get("nome_ctu") or ""),
                albo=str(dati.get("albo") or ""),
                pec_ctu=str(dati.get("pecCtu") or ""),
                quesiti=str(dati.get("quesiti") or ""),
                data_nomina=str(dati.get("dataNomina") or ""),
                data_giuramento=str(dati.get("dataGiuramento") or ""),
                termine_bozza=str(dati.get("termineBozza") or ""),
                termine_osservazioni=str(dati.get("termineOsservazioni") or ""),
                termine_deposito=str(dati.get("termineDeposito") or ""),
            )
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("ctu.incarico_creato", "fascicolo", id_fasc, dettagli=incarico.nome_ctu)
        message = f"Incarico CTU registrato: {incarico.nome_ctu or 'da completare'}."
        return jsonify({"ok": True, "message": message, "messaggio": message, "incarico": _incarico_payload(incarico)})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/aggiorna", methods=["POST"])
    def fascicolo_ctu_aggiorna(id_fasc: str, incarico_id: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        campi = {
            chiave_py: str(dati.get(chiave_js) or "")
            for chiave_js, chiave_py in {
                "stato": "stato", "nomeCtu": "nome_ctu", "quesiti": "quesiti",
                "dataGiuramento": "data_giuramento", "termineBozza": "termine_bozza",
                "termineOsservazioni": "termine_osservazioni", "termineDeposito": "termine_deposito",
            }.items()
            if dati.get(chiave_js) is not None
        }
        try:
            incarico = get_ctu().aggiorna(incarico_id, **campi)
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("ctu.incarico_aggiornato", "fascicolo", id_fasc, dettagli=f"{incarico_id}:{incarico.stato}")
        return jsonify({"ok": True, "message": "Incarico aggiornato.", "incarico": _incarico_payload(incarico)})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/ctp", methods=["POST"])
    def fascicolo_ctu_ctp(id_fasc: str, incarico_id: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or request.form
        try:
            incarico = get_ctu().aggiungi_ctp(
                incarico_id,
                nome=str(dati.get("nome") or ""),
                parte=str(dati.get("parte") or ""),
                email=str(dati.get("email") or ""),
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("ctu.ctp_aggiunto", "fascicolo", id_fasc, dettagli=str(dati.get("nome") or ""))
        return jsonify({"ok": True, "message": "Consulente di parte registrato.", "incarico": _incarico_payload(incarico)})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/proponi-scadenze", methods=["POST"])
    def fascicolo_ctu_proponi_scadenze(id_fasc: str, incarico_id: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        utente = g.get("utente_corrente")
        try:
            creati = get_ctu().proponi_scadenze(
                incarico_id,
                get_scadenziario=get_scadenziario,
                attore=getattr(utente, "username", "") or "",
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        except Exception as exc:
            app.logger.exception("Errore proposte scadenze CTU %s: %s", incarico_id, exc)
            return jsonify({"ok": False, "message": f"Proposte non riuscite: {exc}"}), 200
        audit("ctu.scadenze_proposte", "fascicolo", id_fasc, dettagli=f"{incarico_id}: {creati} proposte")
        message = (
            f"{creati} scadenze proposte in bozza nello scadenziario (da confermare)."
            if creati
            else "Nessuna nuova scadenza da proporre (date mancanti o gia' proposte)."
        )
        return jsonify({"ok": True, "message": message, "messaggio": message, "creati": creati})
