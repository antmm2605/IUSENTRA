"""Route della coda proposte scadenza dalle PEC (conferma/scarto bozze).

Le date lette nei provvedimenti in ingresso (D.M. 44/2011, art. 136 c.p.c.)
diventano scadenze in stato BOZZA: queste route chiudono il ciclo con la
decisione dell'avvocato — conferma (BOZZA -> APERTO) o scarto motivato
(BOZZA -> ANNULLATO) — tracciata in audit.
"""

from __future__ import annotations

from collections.abc import Callable

from flask import Flask, g, jsonify, request

from pct.scadenziario import GestioneScadenziario, TipoTermine
from web.services.scadenza_proposta_agenda import crea_agenda_da_udienza_confermata


def register_scadenziario_proposte_routes(
    app: Flask,
    *,
    get_scadenziario: Callable[[], GestioneScadenziario],
    audit: Callable[..., None],
    sync_pubblica: Callable[[str, str, str], None],
    get_agenda: Callable[[], object] | None = None,
    get_fascicoli: Callable[[], object] | None = None,
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
        agenda_creata = False
        # Alla conferma di un'udienza, l'evento entra anche in agenda collegato al
        # fascicolo: il calendario resta la vista operativa dell'avvocato.
        if scadenza.tipo == TipoTermine.UDIENZA and get_agenda is not None:
            try:
                agenda_creata = crea_agenda_da_udienza_confermata(
                    scadenza,
                    gestione_agenda=get_agenda(),
                    gestione_scadenziario=gs,
                    gestione_fascicoli=get_fascicoli() if get_fascicoli else None,
                    attore=getattr(utente, "username", "") or "",
                )
                if agenda_creata:
                    sync_pubblica("modifica", "agenda", id_sc)
            except Exception:
                agenda_creata = False
        message = f"Proposta confermata: la scadenza del {scadenza.data_scadenza[:10]} è ora operativa."
        if agenda_creata:
            message += " Udienza aggiunta anche in agenda."
        return jsonify({"ok": True, "message": message, "messaggio": message, "id": scadenza.id, "agenda_creata": agenda_creata})

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
