"""Route degli incarichi CTU collegati al fascicolo.

Base normativa: artt. 191-201 c.p.c.; art. 195 c.3 c.p.c. (timeline fissata
dall'ordinanza del giudice). La sezione UI vive nel dettaglio fascicolo; le
scadenze proposte nascono in BOZZA nello scadenziario.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, g, jsonify
from web.services.ctu_commands import apply_ctu_change, governed_ctu_write, legacy_ctu_audit, read_ctu_body

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


def _vacazioni_registro(incarico: Any) -> dict[str, Any]:
    from pct.ctu_compensi.vacazioni import conteggio_giornaliero

    esito = conteggio_giornaliero(incarico.operazioni)
    return {"vacazioni": esito["vacazioni"], "escluse_per_tetto": esito["escluse_per_tetto"]}


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
        "dataDepositoRelazione": incarico.data_deposito_relazione,
        "dataComunicazioneDecreto": incarico.data_comunicazione_decreto,
        "importoLiquidato": incarico.importo_liquidato,
        "operazioni": incarico.operazioni,
        "vacazioniRegistro": _vacazioni_registro(incarico),
        "compensoInput": incarico.compenso_input,
        "stati": [{"value": k, "label": v} for k, v in _STATO_LABEL.items()],
        "actions": {
            "operazioni": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/operazioni",
            "compenso": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/compenso",
            "istanza": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/istanza",
            "deposito": f"/fascicoli/{incarico.fascicolo_id}/deposito/prepara",
            "aggiorna": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/aggiorna",
            "proponiScadenze": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/proponi-scadenze",
            "aggiungiCtp": f"/fascicoli/{incarico.fascicolo_id}/ctu/{incarico.id}/ctp",
        },
    }


def register_ctu_routes(app: Flask, core: dict[str, Any]) -> None:
    get_ctu = core["get_ctu"]
    get_scadenziario = core["get_scadenziario"]
    audit = core["audit"]
    get_fascicoli = core["get_fascicoli"]

    def _permesso(nome: str = "fascicoli.scrivi") -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso(nome))
        except Exception:
            return False

    def _incarico_appartiene(id_fasc: str, incarico_id: str) -> bool:
        if get_fascicoli().get(id_fasc) is None:
            return False
        incarico = get_ctu().get(incarico_id)
        return bool(incarico and incarico.fascicolo_id == id_fasc)

    @app.route("/api/v1/ui/fascicoli/<id_fasc>/ctu")
    def fascicolo_ctu_payload(id_fasc: str):
        utente = g.get("utente_corrente")
        if not utente:
            return jsonify({"ok": False, "message": "Accesso richiesto."}), 403
        if not _permesso("fascicoli.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            if get_fascicoli().get(id_fasc) is None:
                return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
            manager = get_ctu()
            incarichi = manager.per_fascicolo(id_fasc)
            return jsonify({"ok": True, "incarichi": [_incarico_payload(i) for i in incarichi],
                            "writeProtocol": manager.write_protocol})
        except Exception as exc:
            app.logger.exception("Errore payload CTU %s: %s", id_fasc, exc)
            return jsonify({"ok": False, "message": "Lettura degli incarichi CTU non riuscita. Riprova; nessun dato è stato cancellato."}), 503

    @app.route("/fascicoli/<id_fasc>/ctu/nuovo", methods=["POST"])
    @governed_ctu_write(app)
    def fascicolo_ctu_nuovo(id_fasc: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        if get_fascicoli().get(id_fasc) is None:
            return jsonify({"ok": False, "message": "Fascicolo non trovato."}), 404
        dati = read_ctu_body()
        manager = get_ctu()
        def mutate():
            return manager.nuovo(
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
        incarico = apply_ctu_change(manager, "incarico_creato", dati, fascicolo_id=id_fasc, mutate=mutate)
        legacy_ctu_audit(manager, audit, "ctu.incarico_creato", "fascicolo", id_fasc, dettagli=incarico.nome_ctu)
        message = f"Incarico CTU registrato: {incarico.nome_ctu or 'da completare'}."
        return jsonify({"ok": True, "message": message, "messaggio": message, "incarico": _incarico_payload(incarico)})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/aggiorna", methods=["POST"])
    @governed_ctu_write(app)
    def fascicolo_ctu_aggiorna(id_fasc: str, incarico_id: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        if not _incarico_appartiene(id_fasc, incarico_id):
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        dati = read_ctu_body()
        campi = {
            chiave_py: str(dati.get(chiave_js) or "")
            for chiave_js, chiave_py in {
                "stato": "stato", "nomeCtu": "nome_ctu", "quesiti": "quesiti",
                "dataGiuramento": "data_giuramento", "termineBozza": "termine_bozza",
                "termineOsservazioni": "termine_osservazioni", "termineDeposito": "termine_deposito",
                "dataDepositoRelazione": "data_deposito_relazione", "dataComunicazioneDecreto": "data_comunicazione_decreto",
                "importoLiquidato": "importo_liquidato",
            }.items()
            if dati.get(chiave_js) is not None
        }
        try:
            manager = get_ctu()
            incarico = apply_ctu_change(manager, "incarico_aggiornato", dati, fascicolo_id=id_fasc, incarico_id=incarico_id,
                                        mutate=lambda: manager.aggiorna(incarico_id, **campi))
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        legacy_ctu_audit(manager, audit, "ctu.incarico_aggiornato", "fascicolo", id_fasc, dettagli=f"{incarico_id}:{incarico.stato}")
        return jsonify({"ok": True, "message": "Incarico aggiornato.", "incarico": _incarico_payload(incarico)})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/ctp", methods=["POST"])
    @governed_ctu_write(app)
    def fascicolo_ctu_ctp(id_fasc: str, incarico_id: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        if not _incarico_appartiene(id_fasc, incarico_id):
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        dati = read_ctu_body()
        try:
            manager = get_ctu()
            def mutate():
                return manager.aggiungi_ctp(
                    incarico_id,
                    nome=str(dati.get("nome") or ""),
                    parte=str(dati.get("parte") or ""),
                    email=str(dati.get("email") or ""),
                )
            incarico = apply_ctu_change(manager, "ctp_aggiunto", dati, fascicolo_id=id_fasc, incarico_id=incarico_id, mutate=mutate)
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        legacy_ctu_audit(manager, audit, "ctu.ctp_aggiunto", "fascicolo", id_fasc, dettagli=str(dati.get("nome") or ""))
        return jsonify({"ok": True, "message": "Consulente di parte registrato.", "incarico": _incarico_payload(incarico)})

    @app.route("/fascicoli/<id_fasc>/ctu/<incarico_id>/proponi-scadenze", methods=["POST"])
    @governed_ctu_write(app)
    def fascicolo_ctu_proponi_scadenze(id_fasc: str, incarico_id: str):
        if not _permesso():
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        if not _incarico_appartiene(id_fasc, incarico_id):
            return jsonify({"ok": False, "message": "Incarico CTU non trovato."}), 404
        utente = g.get("utente_corrente")
        dati = read_ctu_body()
        manager = get_ctu()
        if manager.write_protocol["persistentCommands"]:
            from pct.ctu_deadline_delivery import deliver_deadlines

            def deliver(conn, saved):
                if saved.get("fascicolo_id") != id_fasc or saved.get("id") != incarico_id:
                    raise ValueError("La consegna delle scadenze appartiene a un incarico differente.")
                return deliver_deadlines(conn, saved, tenant=manager._repository.tenant,
                                         actor=manager._repository.actor)

            apply_ctu_change(manager, "scadenze_proposte", dati, fascicolo_id=id_fasc, incarico_id=incarico_id,
                             mutate=lambda: manager.aggiorna(incarico_id), delivery=deliver)
            delivered = g._ctu_delivery_result
            if not isinstance(delivered, dict) or delivered.get("kind") != "deadlines":
                raise RuntimeError("Riscontro della consegna scadenze CTU assente.")
            creati, aggiornati = delivered["created"], delivered["updated"]
            preservate = sum(item["status"] == "manual_preserved" for item in delivered["items"])
            message = f"Scadenze CTU: {creati} nuove bozze, {aggiornati} bozze aggiornate."
            if preservate:
                message += f" {preservate} scadenze con decisioni già registrate conservate: verifica le date discordanti."
            elif not creati and not aggiornati:
                message = "Scadenze già presenti oppure date non indicate: nessun doppione creato."
            return jsonify({"ok": True, "message": message, "messaggio": message, "creati": creati,
                            "aggiornati": aggiornati, "decisioniConservate": preservate, "delivery": delivered})
        try:
            creati = manager.proponi_scadenze(
                incarico_id,
                get_scadenziario=get_scadenziario,
                attore=getattr(utente, "username", "") or "",
            )
        except KeyError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 404
        audit("ctu.scadenze_proposte", "fascicolo", id_fasc, dettagli=f"{incarico_id}: {creati} proposte")
        message = (
            f"{creati} scadenze proposte in bozza nello scadenziario (da confermare)."
            if creati
            else "Nessuna nuova scadenza da proporre (date mancanti o già proposte)."
        )
        return jsonify({"ok": True, "message": message, "messaggio": message, "creati": creati})
