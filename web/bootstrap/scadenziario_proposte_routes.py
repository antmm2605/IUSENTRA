"""Route della coda proposte scadenza dalle PEC (conferma/scarto bozze).

Le date lette nei provvedimenti in ingresso (D.M. 44/2011, art. 136 c.p.c.)
diventano scadenze in stato BOZZA: queste route chiudono il ciclo con la
decisione dell'avvocato — conferma (BOZZA -> APERTO) o scarto motivato
(BOZZA -> ANNULLATO) — tracciata in audit.
"""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, g, jsonify, request

from pct.scadenziario import GestioneScadenziario


def register_scadenziario_proposte_routes(
    app: Flask,
    *,
    get_scadenziario: Callable[[], GestioneScadenziario],
    audit: Callable[..., None],
    sync_pubblica: Callable[[str, str, str], None],
) -> None:
    """Registra conferma e scarto delle proposte di scadenza in bozza."""

    def _utente_autorizzato():
        utente = g.utente_corrente
        if not utente or not utente.ha_permesso("scadenziario.scrivi"):
            return None
        return utente

    @app.route("/scadenziario/<id_sc>/conferma-proposta", methods=["POST"])
    def conferma_proposta_scadenza(id_sc):
        utente = _utente_autorizzato()
        if utente is None:
            return jsonify({"ok": False, "message": "Permesso insufficiente.", "errore": "Permesso insufficiente."}), 403
        gs = get_scadenziario()
        try:
            scadenza = gs.conferma_bozza(id_sc, attore=getattr(utente, "username", "") or "")
            audit("scadenziario.conferma_proposta", "scadenza", id_sc)
            sync_pubblica("modifica", "scadenze", id_sc)
        except ValueError as e:
            return jsonify({"ok": False, "message": str(e), "errore": str(e)}), 400
        message = f"Proposta confermata: la scadenza del {scadenza.data_scadenza[:10]} è ora operativa."
        return jsonify({"ok": True, "message": message, "messaggio": message, "id": scadenza.id})

    @app.route("/scadenziario/<id_sc>/scarta-proposta", methods=["POST"])
    def scarta_proposta_scadenza(id_sc):
        utente = _utente_autorizzato()
        if utente is None:
            return jsonify({"ok": False, "message": "Permesso insufficiente.", "errore": "Permesso insufficiente."}), 403
        gs = get_scadenziario()
        motivo = (request.form.get("motivo") or (request.get_json(silent=True) or {}).get("motivo") or "").strip()
        try:
            gs.scarta_bozza(id_sc, motivo=motivo, attore=getattr(utente, "username", "") or "")
            audit("scadenziario.scarta_proposta", "scadenza", id_sc, dettagli=motivo[:200])
            sync_pubblica("modifica", "scadenze", id_sc)
        except ValueError as e:
            return jsonify({"ok": False, "message": str(e), "errore": str(e)}), 400
        message = "Proposta scartata: nessuna scadenza operativa creata."
        return jsonify({"ok": True, "message": message, "messaggio": message, "id": id_sc})
