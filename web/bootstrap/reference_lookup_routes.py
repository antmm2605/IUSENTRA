"""Reference and lookup routes extracted from web.app."""

from __future__ import annotations

import os
from collections.abc import Callable

from flask import Flask, g, jsonify, render_template, request

from pct.reginde import ClientReGINde


def register_reference_lookup_routes(
    app: Flask,
    *,
    audit: Callable[..., None],
) -> None:
    """Register lookup routes for uffici, codici fiscali, and tribunali."""

    @app.route("/api/uffici")
    def api_uffici():
        """Autocomplete uffici giudiziari usando la cache aggiornata."""
        try:
            from pct.uffici_giudiziari import get_gestore

            query = request.args.get("q", "").strip()
            tipo = request.args.get("tipo", "")
            try:
                limit = int(request.args.get("limit", "20") or "20")
            except ValueError:
                limit = 20
            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            gestore = get_gestore(cache_path)
            return jsonify(gestore.cerca(query, tipo, limit=limit))
        except Exception as exc:
            app.logger.exception("Errore api_uffici: %s", exc)
            return jsonify([]), 200

    @app.route("/api/uffici/aggiorna", methods=["POST"])
    def api_uffici_aggiorna():
        """Forza l'aggiornamento della cache degli uffici giudiziari."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False, "messaggio": "Non autorizzato"}), 403
        try:
            from pct.uffici_giudiziari import get_gestore

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            gestore = get_gestore(cache_path)
            url_personalizzato = request.json.get("url", "") if request.is_json else ""
            ok, messaggio = gestore.aggiorna(url=url_personalizzato)
            stato = gestore.stato()
            audit("uffici.aggiorna", "sistema", None, dettagli=messaggio)
            return jsonify({"ok": ok, "messaggio": messaggio, "stato": stato})
        except Exception as exc:
            app.logger.exception("Errore api_uffici_aggiorna: %s", exc)
            return jsonify({"ok": False, "messaggio": str(exc)}), 200

    @app.route("/api/uffici/stato")
    def api_uffici_stato():
        """Stato della cache degli uffici giudiziari."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.uffici_giudiziari import get_gestore

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            return jsonify(get_gestore(cache_path).stato())
        except Exception as exc:
            app.logger.exception("Errore api_uffici_stato: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/api/uffici/variazioni")
    def api_uffici_variazioni():
        """Ultimo report di verifica variazioni uffici."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.uffici_giudiziari import get_gestore

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = get_gestore(cache_path).carica_report_variazioni()
            if report is None:
                return jsonify({"ok": False, "errore": "Nessun controllo eseguito ancora"})
            return jsonify(report)
        except Exception as exc:
            app.logger.exception("Errore api_uffici_variazioni: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/api/uffici/variazioni/esegui", methods=["POST"])
    def api_uffici_variazioni_esegui():
        """Avvia manualmente la verifica variazioni uffici."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.uffici_giudiziari import get_gestore

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = get_gestore(cache_path).verifica_variazioni()
            audit(
                "uffici.verifica_variazioni",
                utente.username,
                None,
                dettagli=f"n_variazioni={report.get('n_variazioni', 0)}",
            )
            return jsonify(report)
        except Exception as exc:
            app.logger.exception("Errore api_uffici_variazioni_esegui: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/api/uffici/sync/report")
    def api_uffici_sync_report():
        """Restituisce l'ultimo report di sync multi-sorgente."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.sync_uffici import carica_ultimo_report

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = carica_ultimo_report(cache_path)
            if report is None:
                return jsonify({"ok": False, "errore": "Nessun sync eseguito ancora"})
            return jsonify(report)
        except Exception as exc:
            app.logger.exception("Errore api_uffici_sync_report: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/api/uffici/sync/esegui", methods=["POST"])
    def api_uffici_sync_esegui():
        """Avvia manualmente il sync multi-sorgente degli uffici."""
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("utenti.leggi"):
            return jsonify({"ok": False}), 403
        try:
            from pct.sync_uffici import esegui_sync_completo

            cache_path = os.getenv("PCT_UFFICI_DB", "/data/uffici/uffici_giudiziari.json")
            report = esegui_sync_completo(cache_path)
            audit(
                "uffici.sync_eseguito",
                utente.username,
                None,
                dettagli=(
                    f"n_totale={report.get('n_totale_post', 0)} "
                    f"nuovi={report.get('n_nuovi', 0)} "
                    f"pec={report.get('n_pec_aggiornate', 0)}"
                ),
            )
            return jsonify(report)
        except Exception as exc:
            app.logger.exception("Errore api_uffici_sync_esegui: %s", exc)
            return jsonify({"ok": False, "errore": str(exc)}), 200

    @app.route("/api/cf/decodifica")
    def api_cf_decodifica():
        """Decodifica un codice fiscale e restituisce i dati anagrafici."""
        codice_fiscale = request.args.get("cf", "").strip()
        try:
            from pct.codice_fiscale import decodifica

            risultato = decodifica(codice_fiscale)
            if risultato is None:
                return jsonify({"errore": "CF non valido o troppo corto"}), 200
            return jsonify(risultato)
        except Exception as exc:
            app.logger.exception("Errore api_cf_decodifica: %s", exc)
            return jsonify({"errore": str(exc)}), 200

    @app.route("/tribunali")
    def tribunali():
        reginde = ClientReGINde()
        uffici = reginde.elenca_uffici()
        return render_template("tribunali.html", uffici=uffici)
