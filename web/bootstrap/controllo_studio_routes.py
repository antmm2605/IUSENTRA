"""Rotte del Controllo Studio (/workspace-intelligente): coda unica e azioni dirette.

Lettura: ogni area compare solo a chi ha il permesso di leggerla. Azioni: «Segna fatto» sul
termine (``scadenziario.scrivi``) e «Segna letta» sulla PEC; il resto apre la pagina dove si lavora.
"""

from __future__ import annotations

import json
from typing import Any

from flask import Flask, g, jsonify, request


def register_controllo_studio_routes(app: Flask, core: dict[str, Any]) -> None:
    audit = core["audit"]

    def _puo(permesso: str) -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso(permesso))
        except Exception:
            return False

    def _presidi() -> list[dict]:
        from web.blueprints.api_v1_react import _notification_presidia_rows

        return _notification_presidia_rows(limit=20)

    @app.route("/api/v1/ui/controllo-studio")
    def controllo_studio_payload():
        from web import helpers
        from web.services.controllo_studio_runtime import costruisci

        if not g.get("utente_corrente"):
            return jsonify({"ok": False, "message": "Accesso richiesto."}), 403
        fonti = {"fascicoli": helpers.get_fascicoli, "scadenziario": helpers.get_scadenziario, "agenda": helpers.get_agenda,
                 "wizard_pro": helpers.get_wizard_pro, "email_pec": helpers.get_email_pec, "messaggi": helpers.get_messaggi,
                 "fatturazione": helpers.get_fatturazione, "clienti": helpers.get_clienti}
        try:
            payload = costruisci(fonti, presidi_notifiche=_presidi, puo=_puo)
            payload["puo_completare_scadenze"] = _puo("scadenziario.scrivi")
            return jsonify(payload)
        except Exception:
            app.logger.exception("Controllo Studio non disponibile")
            return jsonify({"ok": False, "message": "Il quadro dello studio non si è caricato: riprova tra poco."}), 200

    @app.route("/api/v1/ui/controllo-studio/scadenze/completa-scadute", methods=["POST"])
    def controllo_studio_completa_scadute():
        from pct.controllo_studio.completamento import completa_scadute
        from web.helpers import _cfg, _studio_db

        if not _puo("scadenziario.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or payload.get("conferma_adempimento") is not True:
            return jsonify({"ok": False, "message": "Conferma prima che tutte le scadenze siano state adempiute."}), 400
        try:
            risultato = completa_scadute(_studio_db("SCADENZIARIO_DB"), _cfg("SCADENZIARIO_DB"), payload.get("ids"),
                                        attore=str(getattr(g.utente_corrente, "username", "")))
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 409
        except RuntimeError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 503
        n = len(risultato["completate"])
        audit("scadenze.completamento_collettivo", "scadenziario", risultato["operazione_id"],
              dettagli=json.dumps({"adempimento_confermato": True, "ids": risultato["completate"],
                                   "completate": n, "gia_completate": risultato["gia_completate"]}, ensure_ascii=False))
        message = f"{n} scadenze segnate come fatte. Restano consultabili nello Scadenziario tra le completate."
        if not risultato["mirror_allineato"]:
            message += " Salvataggio SQL riuscito; copia di archivio da riallineare."
        return jsonify({"ok": True, "message": message, **risultato})

    @app.route("/api/v1/ui/controllo-studio/scadenze/<sid>/completa", methods=["POST"])
    def controllo_studio_completa_scadenza(sid: str):
        from web.helpers import get_scadenziario

        if not _puo("scadenziario.scrivi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            scadenza = get_scadenziario().completa(sid, note="Segnata adempiuta dal Controllo Studio")
        except (KeyError, ValueError):
            return jsonify({"ok": False, "message": "Termine non trovato."}), 404
        audit("scadenza.completata", "scadenza", sid, dettagli=str(getattr(scadenza, "titolo", "") or ""))
        return jsonify({"ok": True, "message": f"«{scadenza.titolo}» segnato come adempiuto."})

    @app.route("/api/v1/ui/controllo-studio/pec/<eid>/letta", methods=["POST"])
    def controllo_studio_pec_letta(eid: str):
        from web.helpers import get_email_pec

        if not _puo("messaggi.leggi"):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        gestore = get_email_pec()
        if not any(str(e.id) == eid for e in gestore.tutte(cartella="INBOX")):
            return jsonify({"ok": False, "message": "PEC non trovata."}), 404
        gestore.marca_letta(eid)
        audit("pec.letta", "email", eid, dettagli="dal Controllo Studio")
        return jsonify({"ok": True, "message": "PEC segnata come letta."})


__all__ = ["register_controllo_studio_routes"]
