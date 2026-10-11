"""Rotte JSON della Preparazione udienza (pagine /wizard-pro/…).

Lettura con ``agenda.leggi``; avvio, salvataggi ed esito con ``agenda.scrivi``. L'esito crea
anche udienza di rinvio e termini: servono i permessi di agenda e scadenziario.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request
from web.services.preparazione_udienza_http_commands import command_context, command_input, confirm, governed_write, persistent


def register_preparazione_udienza_routes(app: Flask, core: dict[str, Any]) -> None:
    audit = core["audit"]

    @app.teardown_request
    def _close_preparazioni_database(error):
        from web.services.preparazione_udienza_sql_runtime import close_database
        close_database()

    def _puo(*permessi: str) -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente) and all(utente.ha_permesso(p) for p in permessi)
        except Exception:
            return False

    def _oggi():
        return datetime.now(ZoneInfo("Europe/Rome")).date()

    def _repo():
        from web import helpers

        return {"agenda": helpers.get_agenda(), "fascicoli": helpers.get_fascicoli(), "preparazioni": helpers.get_wizard_pro()}

    def _sessione(sid: str):
        from web.helpers import get_wizard_pro

        return get_wizard_pro().carica(sid)

    def _utente() -> str:
        utente = g.get("utente_corrente")
        return str(getattr(utente, "nome_completo", "") or getattr(utente, "username", "") or "")

    def _dettaglio(sessione):
        from web.helpers import get_scadenziario
        from web.services.preparazione_udienza_runtime import dettaglio

        r = _repo()
        payload = dettaglio(sessione, agenda=r["agenda"], fascicoli=r["fascicoli"], scadenziario=get_scadenziario(), oggi=_oggi())
        if persistent(r["preparazioni"]):
            payload.update(writeProtocol=r["preparazioni"].write_protocol, revision=sessione.sql_revision)
        payload["puoRegistrareEsito"] = _puo("agenda.scrivi", "scadenziario.scrivi", "fascicoli.scrivi")
        return payload

    @app.route("/api/v1/ui/preparazione-udienza")
    def preparazione_udienza_elenco():
        from web.services.preparazione_udienza_elenco import elenco

        if not _puo("agenda.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        repositories = _repo()
        protocol = repositories["preparazioni"].write_protocol if persistent(repositories["preparazioni"]) else {"persistentCommands": False}
        return jsonify({**elenco(**repositories, oggi=_oggi()), "puoModificare": _puo("agenda.scrivi"), "writeProtocol": protocol})

    @app.route("/api/v1/ui/preparazione-udienza/avvia", methods=["POST"])
    @governed_write(app)
    def preparazione_udienza_avvia():
        from web.services.preparazione_udienza_elenco import avvia

        if not _puo("agenda.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or {}
        repositories = _repo()
        manager = repositories["preparazioni"]
        try:
            if persistent(manager):
                command, _, intent = command_input(dati, start=True)
                command_context(manager, "", command, 0)
                if set(intent) - {"idAppuntamento", "idFascicolo"}:
                    raise ValueError("Campi dell'avvio non previsti.")
                result = manager.start(fascicolo_id=intent.get("idFascicolo", ""),
                    appuntamento_id=intent.get("idAppuntamento", ""), command_key=command, avvocato=_utente())
                sessione = confirm(manager, result, command)
            else:
                sessione = avvia(**repositories, id_appuntamento=str(dati.get("idAppuntamento") or ""),
                                 id_fascicolo=str(dati.get("idFascicolo") or ""), avvocato=_utente())
        except ValueError as exc:
            if persistent(manager):
                raise
            return jsonify({"ok": False, "message": str(exc)}), 400
        if not persistent(manager):
            audit("udienza.preparazione_avviata", "fascicolo", sessione.id_fascicolo, dettagli=sessione.id)
        elif manager.carica(sessione.id) is None:
            return jsonify(ok=True, message="Il precedente avvio era confermato, ma la preparazione è stata successivamente eliminata.", redirect="/wizard-pro/")
        passo = 5 if sessione.stato == "completato" else max(1, min(int(sessione.step_corrente or 1), 5))
        return jsonify({"ok": True, "message": "Preparazione aperta.", "redirect": f"/wizard-pro/{sessione.id}/step/{passo}"})

    @app.route("/api/v1/ui/preparazione-udienza/<sid>")
    def preparazione_udienza_dettaglio(sid: str):
        if not _puo("agenda.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        sessione = _sessione(sid)
        if sessione is None:
            return jsonify({"ok": False, "message": "Preparazione non trovata."}), 404
        if getattr(sessione, "reference_issue", ""):
            return jsonify(ok=False, message=sessione.reference_issue +
                           " Consulta la preparazione storica conservata nell'elenco.",
                           href="/wizard-pro/"), 409
        return jsonify({**_dettaglio(sessione), "puoModificare": _puo("agenda.scrivi")})

    @app.route("/api/v1/ui/preparazione-udienza/<sid>/<azione>", methods=["POST"])
    @governed_write(app)
    def preparazione_udienza_azione(sid: str, azione: str):
        from web.helpers import get_scadenziario, get_wizard_pro
        from web.services import preparazione_udienza_runtime as rt

        if not _puo("agenda.scrivi") or (azione == "esito" and not _puo("scadenziario.scrivi", "fascicoli.scrivi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        sessione = _sessione(sid)
        if sessione is None:
            return jsonify({"ok": False, "message": "Preparazione non trovata."}), 404
        dati = request.get_json(silent=True) or {}
        manager = get_wizard_pro()
        if persistent(manager):
            if azione not in {"passo", "documento", "documento-extra", "verifica", "esito"}:
                return jsonify(ok=False, message="Azione non prevista."), 404
            command, revision, intent = command_input(dati)
            command_context(manager, sid, command, revision)
            result = manager.execute(sid, azione, intent, command_key=command, expected_revision=revision, today=_oggi())
            sessione = confirm(manager, result, command)
            creati = result.get("effects", {}).get("created", [])
            return jsonify(ok=True, message="Esito registrato." if azione == "esito" else "Salvato.",
                           creati=creati, dati=_dettaglio(sessione))
        messaggio, creati = "Salvato.", []
        try:
            if azione == "passo":
                passo = int(dati.get("passo") or 0)
                rt.salva_passo(sessione, passo, dati.get("campi") or {}, conferma=bool(dati.get("conferma")))
                messaggio = "Passo completato." if dati.get("conferma") else "Salvato."
            elif azione == "documento":
                rt.imposta_documento(sessione, int(dati.get("indice", -1)), str(dati.get("stato") or ""))
            elif azione == "documento-extra":
                rt.aggiungi_documento(sessione, str(dati.get("etichetta") or ""))
            elif azione == "verifica":
                rt.imposta_verifica(sessione, str(dati.get("id") or ""), bool(dati.get("fatta")))
            elif azione == "esito":
                r = _repo()
                creati = rt.registra_esito(sessione, dati, agenda=r["agenda"], fascicoli=r["fascicoli"], scadenziario=get_scadenziario(),
                                           utente=_utente(), oggi=_oggi())
                messaggio = "Esito registrato" + (": creati " + ", ".join(creati) + "." if creati else ".")
            else:
                return jsonify({"ok": False, "message": "Azione non prevista."}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        get_wizard_pro().salva(sessione)
        if azione == "esito":
            audit("udienza.esito", "fascicolo", sessione.id_fascicolo, dettagli=f"{sessione.id}: {sessione.esito}")
        return jsonify({"ok": True, "message": messaggio, "creati": creati, "dati": _dettaglio(sessione)})


__all__ = ["register_preparazione_udienza_routes"]
