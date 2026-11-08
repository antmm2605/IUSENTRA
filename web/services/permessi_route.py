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

from flask import flash, g, jsonify, redirect

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
