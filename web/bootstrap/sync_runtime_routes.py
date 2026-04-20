"""Runtime sync, PEC polling, and OCR routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from flask import Flask, Response, abort, flash, g, jsonify, redirect, request, session, url_for


def register_sync_runtime_routes(
    app: Flask,
    *,
    sync_manager: Any,
    get_fascicoli: Callable[[], object],
    get_utenti: Callable[[], object],
    audit: Callable[..., None],
) -> None:
    """Register realtime sync and operational background routes."""

    def _current_user():
        utente = getattr(g, "utente_corrente", None)
        if utente is not None:
            return utente
        user_id = session.get("user_id") or session.get("utente_id")
        if not user_id:
            return None
        try:
            return get_utenti().get(str(user_id))
        except Exception:
            return None

    @app.route("/api/eventi")
    def api_eventi():
        utente = _current_user()
        if not utente:
            return jsonify({"errore": "Non autenticato"}), 401

        user_key = utente.username if utente else ""
        client_id, event_queue = sync_manager.subscribe(user_key=user_key)
        sync_manager.notifica_connessi()

        def genera():
            yield from sync_manager.sse_stream(client_id, event_queue)

        return Response(
            genera(),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-store",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.route("/api/sync/stato")
    def api_sync_stato():
        try:
            return jsonify(
                {
                    "connessi": sync_manager.n_connessi,
                    "versioni": {
                        "clienti": sync_manager.versione_file(app.config["CLIENTI_DB"]),
                        "fascicoli": sync_manager.versione_file(app.config["FASCICOLI_DB"]),
                        "scadenze": sync_manager.versione_file(app.config["SCADENZIARIO_DB"]),
                        "agenda": sync_manager.versione_file(app.config["AGENDA_DB"]),
                        "messaggi": sync_manager.versione_file(app.config["MESSAGGI_DB"]),
                    },
                }
            )
        except Exception as e:
            app.logger.exception("Errore api_sync_stato: %s", e)
            return jsonify({"errore": str(e)})

    @app.route("/api/sync/broadcast", methods=["POST"])
    def api_sync_broadcast():
        utente = _current_user()
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"errore": "Non autorizzato"}), 403
        try:
            msg = request.json.get("messaggio", "") if request.is_json else request.form.get("messaggio", "")
            if not msg:
                return jsonify({"errore": "Messaggio obbligatorio"}), 400
            n = sync_manager.pubblica_broadcast(msg, utente=utente.username)
            audit("sync.broadcast", dettagli=msg)
            return jsonify({"ok": True, "raggiunti": n})
        except Exception as e:
            app.logger.exception("Errore api_sync_broadcast: %s", e)
            return jsonify({"ok": False, "errore": str(e)})

    @app.route("/api/pec/poll-cancelleria", methods=["POST"])
    def api_pec_poll_cancelleria():
        try:
            from pct.config_studio import GestioneConfigStudio
            from pct.email_client import (
                GestioneEmailRicevute,
                riassunto_auto_esiti,
                sincronizza_pec_e_fascicoli,
            )
            from pct.fascicoli import GestioneFascicoli

            utente = _current_user()
            if not utente or not utente.ha_permesso("fascicoli.scrivi"):
                return jsonify({"ok": False, "errore": "Non autorizzato"}), 403

            fascicoli_db = app.config.get("FASCICOLI_DB", "./fascicoli/fascicoli.json")
            if not os.path.exists(fascicoli_db):
                return jsonify({"ok": False, "errore": "Database fascicoli non trovato"}), 404

            payload = request.get_json(silent=True) or {}
            fascicolo_id = str(payload.get("id_fascicolo") or "").strip()

            config_pec = None
            try:
                config_studio_db = app.config.get("STUDIO_CONFIG") or app.config.get(
                    "CONFIG_STUDIO_DB",
                    "./config/studio.json",
                )
                cfg_studio = GestioneConfigStudio(config_path=config_studio_db)
                config_pec = getattr(cfg_studio.config, "pec", None)
                if config_pec and (
                    not getattr(config_pec, "imap_host", "")
                    or not getattr(config_pec, "indirizzo", "")
                ):
                    config_pec = None
            except Exception as e:
                app.logger.debug("Config PEC non disponibile: %s", e)

            if not config_pec:
                return jsonify(
                    {
                        "ok": False,
                        "errore": "PEC IMAP non configurata. Vai in Impostazioni -> PEC per configurarla.",
                    }
                )

            gf = GestioneFascicoli(db_path=fascicoli_db)
            ge = GestioneEmailRicevute(
                db_path=app.config.get(
                    "EMAIL_CASELLA_DB",
                    os.environ.get("PCT_EMAIL_DB", "./email/casella.json"),
                )
            )
            state_path = os.path.join(
                os.path.dirname(os.path.abspath(fascicoli_db)),
                "pec_cancelleria_state.json",
            )
            workflow = sincronizza_pec_e_fascicoli(
                gestione_email=ge,
                gestione_fascicoli=gf,
                config_pec=config_pec,
                fascicolo_id=fascicolo_id or None,
                state_path=state_path,
                limite=100,
            )
            sync_result = workflow.get("sync", {}) or {}
            auto_log = workflow.get("auto_esiti", []) or []
            auto_summary = riassunto_auto_esiti(auto_log)
            report = workflow.get("poll", {}) or {
                "trovati": 0,
                "associati": 0,
                "duplicati": 0,
                "errori": 0,
            }
            sync_errore = str(sync_result.get("errore") or "").strip()
            pst_in_attesa = sum(
                1 for em in ge._carica().values()
                if em.e_pst and not em.auto_registrata
            )

            if report["associati"]:
                msg = (
                    f"{report['associati']} comunicazion{'e' if report['associati'] == 1 else 'i'} "
                    f"caricata{'.' if report['associati'] == 1 else '.'}"
                )
            elif report["duplicati"]:
                msg = (
                    f"{report['duplicati']} comunicazion{'e' if report['duplicati'] == 1 else 'i'} "
                    f"già present{'e' if report['duplicati'] == 1 else 'i'} nel fascicolo selezionato."
                )
            elif auto_summary["aggiornati"]:
                msg = f"Workflow PEC completato: {auto_summary['aggiornati']} esiti deposito aggiornati."
            elif auto_summary["non_abbinati"]:
                msg = f"{auto_summary['non_abbinati']} PEC PST restano in attesa di abbinamento ai depositi."
            elif sync_result.get("nuove"):
                msg = f"Sincronizzazione PEC completata: {sync_result.get('nuove', 0)} email nuove."
            elif report["trovati"]:
                msg = "Nessuna comunicazione nuova trovata (già tutte caricate)."
            else:
                msg = "Nessuna email di cancelleria trovata nella casella PEC."
            if pst_in_attesa and not auto_summary["non_abbinati"]:
                msg = f"{msg} PEC PST ancora da verificare: {pst_in_attesa}."
            if sync_errore:
                msg = f"{msg} Sincronizzazione IMAP non completata."

            audit("pec.poll_cancelleria", dettagli=str(report))
            app.logger.info(
                "Workflow PEC manuale: %d nuove email, %d esiti, %d comunicazioni, %d errori",
                sync_result.get("nuove", 0),
                len(auto_log),
                report["associati"],
                report["errori"],
            )
            return jsonify(
                {
                    "ok": True,
                    "messaggio": msg,
                    "report": report,
                    "nuove": sync_result.get("nuove", 0),
                    "pst_trovate": sync_result.get("pst_trovate", 0),
                    "esiti_aggiornati": auto_summary["aggiornati"],
                    "non_abbinati": auto_summary["non_abbinati"],
                    "pst_in_attesa": pst_in_attesa,
                    "log": auto_log,
                    "sync_errore": sync_errore,
                    "warning": bool(sync_errore),
                }
            )
        except Exception as e:
            app.logger.exception("Errore api_pec_poll_cancelleria: %s", e)
            return jsonify({"ok": False, "errore": str(e)})

    @app.route("/fascicoli/<id_fasc>/documenti/<id_doc>/ocr", methods=["POST"])
    def ocr_documento(id_fasc, id_doc):
        gf = get_fascicoli()
        fascicolo = gf.get(id_fasc)
        if not fascicolo:
            abort(404)
        doc = next((d for d in getattr(fascicolo, "documenti", []) if d.id == id_doc), None)
        if not doc:
            abort(404)
        from pct.ocr import estrai_testo
        from web.helpers import get_indice

        percorso = gf.percorso_documento(id_fasc, id_doc)
        testo = estrai_testo(percorso) if percorso else ""
        if testo:
            try:
                indice = get_indice()
                indice.indicizza(
                    tipo="documento",
                    id=f"{id_fasc}_{id_doc}",
                    titolo=doc.nome_file,
                    testo=testo,
                    meta={"id_fascicolo": id_fasc},
                )
            except Exception:
                pass
            flash(f"Testo estratto dal documento ({len(testo)} caratteri) e reso ricercabile.", "success")
        else:
            flash("Nessun testo estraibile da questo documento.", "warning")
        return redirect(url_for("dettaglio_fascicolo", id_fascicolo=id_fasc))
