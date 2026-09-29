"""Rotte JSON della Preparazione udienza (pagine /wizard-pro/…).

Lettura con ``agenda.leggi``; avvio, salvataggi ed esito con ``agenda.scrivi``. L'esito crea
anche udienza di rinvio e termini: servono i permessi di agenda e scadenziario.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request


def register_preparazione_udienza_routes(app: Flask, core: dict[str, Any]) -> None:
    audit = core["audit"]

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
        return dettaglio(sessione, agenda=r["agenda"], fascicoli=r["fascicoli"], scadenziario=get_scadenziario(), oggi=_oggi())

    @app.route("/api/v1/ui/preparazione-udienza")
    def preparazione_udienza_elenco():
        from web.services.preparazione_udienza_elenco import elenco

        if not _puo("agenda.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        return jsonify({**elenco(**_repo(), oggi=_oggi()), "puoModificare": _puo("agenda.scrivi")})

    @app.route("/api/v1/ui/preparazione-udienza/avvia", methods=["POST"])
    def preparazione_udienza_avvia():
        from web.services.preparazione_udienza_elenco import avvia

        if not _puo("agenda.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        dati = request.get_json(silent=True) or {}
        try:
            sessione = avvia(**_repo(), id_appuntamento=str(dati.get("idAppuntamento") or ""), id_fascicolo=str(dati.get("idFascicolo") or ""),
                             avvocato=_utente())
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 400
        audit("udienza.preparazione_avviata", "fascicolo", sessione.id_fascicolo, dettagli=sessione.id)
        passo = 5 if sessione.stato == "completato" else max(1, min(int(sessione.step_corrente or 1), 5))
        return jsonify({"ok": True, "message": "Preparazione aperta.", "redirect": f"/wizard-pro/{sessione.id}/step/{passo}"})

    @app.route("/api/v1/ui/preparazione-udienza/<sid>")
    def preparazione_udienza_dettaglio(sid: str):
        if not _puo("agenda.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        sessione = _sessione(sid)
        if sessione is None:
            return jsonify({"ok": False, "message": "Preparazione non trovata."}), 404
        return jsonify({**_dettaglio(sessione), "puoModificare": _puo("agenda.scrivi")})

    @app.route("/api/v1/ui/preparazione-udienza/<sid>/<azione>", methods=["POST"])
    def preparazione_udienza_azione(sid: str, azione: str):
        from web.helpers import get_scadenziario, get_wizard_pro
        from web.services import preparazione_udienza_runtime as rt

        if not _puo("agenda.scrivi") or (azione == "esito" and not _puo("scadenziario.scrivi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        sessione = _sessione(sid)
        if sessione is None:
            return jsonify({"ok": False, "message": "Preparazione non trovata."}), 404
        dati = request.get_json(silent=True) or {}
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
