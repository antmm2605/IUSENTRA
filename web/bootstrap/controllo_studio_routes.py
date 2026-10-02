"""Rotte del Controllo Studio (/workspace-intelligente): coda unica e azioni dirette.

Lettura: ogni area compare solo a chi ha il permesso di leggerla. Azioni: «Segna fatto» sul
termine (``scadenziario.scrivi``) e «Segna letta» sulla PEC; il resto apre la pagina dove si lavora.
"""

from __future__ import annotations

import json
from typing import Any

from flask import Flask, g, jsonify, request


def register_controllo_studio_routes(app: Flask, core: dict[str, Any]) -> None:
    from web.bootstrap.viewer_editor_routes import register_viewer_editor_routes

    register_viewer_editor_routes(app)
    audit = core["audit"]

    def _puo(permesso: str) -> bool:
        utente = g.get("utente_corrente")
        try:
            return bool(utente and utente.ha_permesso(permesso))
        except Exception:
            return False

    def _presidi() -> list[dict]:
        from web.services.controllo_studio_presidi import righe_presidi

        return righe_presidi()

    @app.route("/api/v1/ui/controllo-studio/discordanze")
    def controllo_studio_discordanze():
        if not (_puo("fascicoli.leggi") and _puo("clienti.leggi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        from web.services.discordanze_letture_runtime import riepilogo_discordanze

        try:
            pagina = int(request.args.get("pagina", "1"))
        except (TypeError,ValueError):
            return jsonify({"ok": False, "message": "Pagina non valida."}), 400
        if pagina < 1 or pagina > 10000:
            return jsonify({"ok": False, "message": "Pagina non valida."}), 400
        return jsonify(riepilogo_discordanze(pagina))

    @app.route("/api/v1/ui/controllo-studio/conoscenza-notifiche")
    def controllo_studio_conoscenza_notifiche():
        from pct.notifiche_conoscenza import consulta

        if not (_puo("fascicoli.leggi") and _puo("messaggi.leggi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        try:
            pagina = int(request.args.get("pagina", "1"))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "message": "Pagina non valida."}), 400
        return jsonify(consulta(request.args.get("q", ""), pagina=pagina))

    @app.route("/api/v1/ui/controllo-studio/conoscenza-notifiche/fonti/<codice>")
    def controllo_studio_fonte_notifiche(codice: str):
        import hashlib
        from pathlib import Path
        from pct.notifiche_conoscenza import fonti

        if not (_puo("fascicoli.leggi") and _puo("messaggi.leggi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        fonte = fonti().get(codice)
        if not fonte:
            return jsonify({"ok": False, "message": "Fonte non disponibile."}), 404
        path = Path(__file__).resolve().parents[2] / fonte["file"]
        data = path.read_bytes() if path.is_file() else b""
        if not data or hashlib.sha256(data).hexdigest() != fonte["sha256"]:
            return jsonify({"ok": False, "message": "La copia della fonte richiede una verifica di integrità."}), 503
        from web.services.notifiche_fonte_reader import visualizza_fonte_notifiche
        return visualizza_fonte_notifiche(data, fonte.get("titolo") or codice, path.name)

    @app.route("/api/v1/ui/controllo-studio/fascicoli/<fid>/verifica-notifiche/<did>", methods=["POST"])
    def controllo_studio_salva_verifica(fid: str, did: str):
        from web.helpers import get_fascicoli
        from web.services.verifica_notifiche_contesto import repository, valida
        from web.services.verifica_notifiche_runtime import verifica_fascicolo
        if not (_puo("fascicoli.leggi") and _puo("fascicoli.scrivi") and _puo("messaggi.leggi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        fascicolo = get_fascicoli().get(fid)
        if fascicolo is None:
            return jsonify({"ok": False, "message": "Fascicolo non disponibile."}), 404
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"ok": False, "message": "Dati della verifica non validi."}), 400
        try:
            dati = valida(fascicolo, did, payload)
            revisione = payload.get("revisione", 0)
            if not isinstance(revisione, int) or isinstance(revisione, bool) or revisione < 0:
                raise ValueError("Revisione non valida.")
            repository().salva(fid, did, dati, attore=str(getattr(g.utente_corrente, "username", "")), revisione=revisione)
        except ValueError as exc:
            return jsonify({"ok": False, "message": str(exc)}), 409
        audit("notifiche.dati_verificati", "fascicolo", fid, dettagli=did)
        return jsonify(verifica_fascicolo(fascicolo))

    @app.route("/api/v1/ui/controllo-studio/fascicoli/<fid>/verifica-notifiche")
    def controllo_studio_verifica_notifiche(fid: str):
        from web.helpers import get_fascicoli
        from web.services.verifica_notifiche_runtime import verifica_fascicolo

        if not (_puo("fascicoli.leggi") and _puo("messaggi.leggi")):
            return jsonify({"ok": False, "message": "Permesso insufficiente."}), 403
        fascicolo = get_fascicoli().get(fid)
        if fascicolo is None:
            return jsonify({"ok": False, "message": "Fascicolo non disponibile."}), 404
        try:
            return jsonify(verifica_fascicolo(fascicolo))
        except Exception:
            app.logger.exception("Verifica notifiche non disponibile")
            return jsonify({"ok": False, "message": "Verifica documentale non disponibile: riprova."}), 503

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
