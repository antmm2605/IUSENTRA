"""Controllo dei permessi per le rotte storiche (moduli classici e azioni POST).

Le rotte React passano da ``_session_user_can`` in ``api_v1_react``; le rotte
storiche dei fascicoli, dei clienti, dei backup e del registro privacy usavano
solo l'accesso, senza verificare il permesso dell'azione. Questo modulo dà una
risposta unica: JSON 403 per le chiamate dell'interfaccia, avviso e rimando
per i moduli classici.

Base: art. 32 GDPR (misure tecniche adeguate, controllo degli accessi) e
art. 2-quaterdecies D.Lgs. 196/2003 (persone autorizzate al trattamento).
"""

from __future__ import annotations

from typing import Any

from flask import flash, g, jsonify, redirect, url_for

from web.services.request_mode import richiede_json


def utente_ha_permesso(permesso: str) -> bool:
    utente = getattr(g, "utente_corrente", None)
    return bool(utente is not None and utente.ha_permesso(permesso))


def permesso_negato(permesso: str, messaggio: str, rimando: str):
    """Risposta 403 se l'utente corrente non ha ``permesso``, altrimenti ``None``."""
    if utente_ha_permesso(permesso):
        return None
    if richiede_json():
        return jsonify({"ok": False, "message": messaggio, "messaggio": messaggio, "permesso": permesso}), 403
    flash(messaggio, "danger")
    return redirect(rimando)


_MESSAGGI_FASCICOLI = {
    "fascicoli.scrivi": "Non hai il permesso per modificare i fascicoli.",
    "fascicoli.archivia": "Non hai il permesso per archiviare o ripristinare i fascicoli.",
    "fascicoli.elimina": "Non hai il permesso per eliminare i fascicoli.",
}


def permesso_fascicolo_negato(permesso: str, id_fasc: str = ""):
    """Rifiuto per le azioni dei fascicoli: rimanda al fascicolo o all'elenco."""
    rimando = url_for("dettaglio_fascicolo", id_fasc=id_fasc) if id_fasc else url_for("lista_fascicoli")
    return permesso_negato(permesso, _MESSAGGI_FASCICOLI[permesso], rimando)


def descrizione_fascicolo(fascicolo: Any) -> str:
    """Numero, titolo e cliente del fascicolo per il registro delle attività."""
    parti = (str(getattr(fascicolo, campo, "") or "").strip() for campo in ("numero", "titolo", "nome_cliente"))
    return " - ".join(parte for parte in parti if parte)
