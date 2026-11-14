"""API JSON dei collaboratori del singolo fascicolo (pannello React nella sezione «Pratica»).

Sostituiscono la pagina classica ``fascicoli/collaboratori_fascicolo.html`` con gli stessi
permessi (``fascicoli.scrivi`` oppure ruolo GESTORE sul fascicolo), gli stessi gestori del
tenant corrente e le stesse voci di audit (``condivisione.fascicolo.condividi`` / ``revoca``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from flask import Flask, g, jsonify, request

from pct.condivisione import RuoloCondivisione
from web.services.react_condivisioni_bridge import build_matter_collaborators_payload

ROME_TZ = ZoneInfo("Europe/Rome")


def register_collaboratori_fascicolo_api(
    app: Flask,
    *,
    get_condivisioni: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_utenti: Callable[[], Any],
    audit: Callable[..., None],
) -> None:
    def _contesto(id_fasc: str):
        """Utente, fascicolo ed errore: stesso controllo della pagina classica."""
        utente = getattr(g, "utente_corrente", None)
        if utente is None:
            return None, None, (jsonify({"errore": "Autenticazione richiesta.", "code": "authentication_required"}), 401)
        fascicolo = get_fascicoli().get(id_fasc)
        if not fascicolo:
            return utente, None, (jsonify({"errore": "Fascicolo non trovato."}), 404)
        puo_gestire = utente.ha_permesso("fascicoli.scrivi") or get_condivisioni().ha_accesso_fascicolo(
            utente.id, id_fasc, RuoloCondivisione.GESTORE
        )
        if not puo_gestire:
            return utente, fascicolo, (
                jsonify({"errore": "Non hai il permesso di gestire i collaboratori di questo fascicolo.", "code": "forbidden"}),
                403,
            )
        return utente, fascicolo, None

    @app.route("/api/v1/fascicoli/<id_fasc>/collaboratori", methods=["GET"])
    def api_collaboratori_fascicolo(id_fasc: str):
        utente, fascicolo, errore = _contesto(id_fasc)
        if errore:
            return errore
        return jsonify(
            build_matter_collaborators_payload(
                fascicolo=fascicolo,
                get_condivisioni=get_condivisioni,
                get_utenti=get_utenti,
                current_user=utente,
            )
        )

    @app.route("/api/v1/fascicoli/<id_fasc>/collaboratori", methods=["POST"])
    def api_condividi_fascicolo(id_fasc: str):
        utente, fascicolo, errore = _contesto(id_fasc)
        if errore:
            return errore
        data = request.get_json(silent=True) or {}
        id_dest = str(data.get("id_utente") or "").strip()
        if not id_dest:
            return jsonify({"errore": "Seleziona un collaboratore."}), 400
        if id_dest == utente.id:
            return jsonify({"errore": "Il profilo in uso non può essere aggiunto come collaboratore."}), 400
        utente_dest = get_utenti().get(id_dest)
        if not utente_dest or not getattr(utente_dest, "attivo", True):
            return jsonify({"errore": "Collaboratore non disponibile."}), 404
        ruolo_str = str(data.get("ruolo") or RuoloCondivisione.LETTURA.value).strip().upper()
        try:
            ruolo = RuoloCondivisione(ruolo_str)
        except ValueError:
            return jsonify({"errore": "Ruolo non valido."}), 400
        data_scadenza = str(data.get("data_scadenza") or "").strip()
        if data_scadenza:
            try:
                if date.fromisoformat(data_scadenza) < datetime.now(ROME_TZ).date():
                    return jsonify({"errore": "La scadenza non può essere nel passato."}), 400
            except ValueError:
                return jsonify({"errore": "La data di scadenza non è valida."}), 400
        raw_tags = data.get("tags") or []
        if isinstance(raw_tags, str):
            raw_tags = raw_tags.split(",")
        if not isinstance(raw_tags, list):
            return jsonify({"errore": "I tag indicati non sono validi."}), 400
        tags = [str(tag).strip()[:50] for tag in raw_tags if str(tag).strip()][:10]
        nome_dest = utente_dest.nome_completo or utente_dest.username
        get_condivisioni().condividi_fascicolo(
            id_fascicolo=id_fasc,
            id_cliente=fascicolo.id_cliente,
            id_utente=utente_dest.id,
            username=utente_dest.username,
            nome_completo=nome_dest,
            ruolo=ruolo,
            condiviso_da=utente.username,
            note=str(data.get("note") or "").strip()[:1000],
            data_scadenza=data_scadenza,
            tags=tags,
        )
        audit(
            "condivisione.fascicolo.condividi",
            "fascicolo",
            id_fasc,
            dettagli=f"→ {utente_dest.username} [{ruolo.value}]",
        )
        return jsonify({"stato": "ok", "messaggio": f"Fascicolo condiviso con {nome_dest}."}), 201

    @app.route("/api/v1/fascicoli/<id_fasc>/collaboratori/<id_utente>", methods=["DELETE"])
    def api_revoca_collaboratore_fascicolo(id_fasc: str, id_utente: str):
        _utente, _fascicolo, errore = _contesto(id_fasc)
        if errore:
            return errore
        utente_dest = get_utenti().get(id_utente)
        username_dest = utente_dest.username if utente_dest else id_utente
        nome_dest = (utente_dest.nome_completo or utente_dest.username) if utente_dest else id_utente
        if not get_condivisioni().revoca_fascicolo(id_fasc, id_utente):
            return jsonify({"errore": "Accesso non trovato."}), 404
        audit("condivisione.fascicolo.revoca", "fascicolo", id_fasc, dettagli=f"→ {username_dest}")
        return jsonify({"stato": "ok", "messaggio": f"Accesso al fascicolo revocato per {nome_dest}."}), 200
