"""Ricevuta telematica pagata prima dell'iscrizione a ruolo (verifica di produzione del 31/10/2026, punto V16)."""

from __future__ import annotations

from pct.archivio_letture.verifica_economica import identita_ricevuta_prima_del_ruolo

SENZA_RUOLO = {"codice": "rg_economico", "esito": "attenzione", "dettaglio": "Numero e anno RG della pratica non presenti nel contenuto."}
UFFICIO = {"codice": "ufficio_economico", "esito": "attenzione", "dettaglio": "non confermato", "conflitto": False}
CLIENTE = {"codice": "cliente_economico", "esito": "ok", "dettaglio": "Cliente presente"}
CF = {"codice": "cf_economico", "esito": "ok", "dettaglio": "Codice fiscale della parte concordante o non dichiarato nella fonte."}


def _esiti(prove):
    return {p["codice"]: p["esito"] for p in prove}


def test_ricevuta_senza_ruolo_con_cliente_riscontrato():
    esito = _esiti(identita_ricevuta_prima_del_ruolo([CF, UFFICIO, CLIENTE, SENZA_RUOLO]))
    assert esito == {"cf_economico": "ok", "ufficio_economico": "ok", "cliente_economico": "ok", "rg_economico": "ok"}


def test_casi_in_cui_non_si_riscontra():
    altro_ruolo = {**SENZA_RUOLO, "dettaglio": "RG rilevati nel contenuto: 12/2025; RG del fascicolo 7/2026 non confermato."}
    assert _esiti(identita_ricevuta_prima_del_ruolo([CF, UFFICIO, CLIENTE, altro_ruolo]))["rg_economico"] == "attenzione"
    senza_cliente = {**CLIENTE, "esito": "attenzione"}
    cf_assente = {**CF, "esito": "attenzione"}
    assert _esiti(identita_ricevuta_prima_del_ruolo([cf_assente, UFFICIO, senza_cliente, SENZA_RUOLO]))["rg_economico"] == "attenzione"
    conflitto = {**UFFICIO, "conflitto": True}
    assert _esiti(identita_ricevuta_prima_del_ruolo([CF, conflitto, CLIENTE, SENZA_RUOLO]))["ufficio_economico"] == "attenzione"
    # Il solo codice fiscale concordante basta come riscontro della persona.
    assert _esiti(identita_ricevuta_prima_del_ruolo([CF, UFFICIO, senza_cliente, SENZA_RUOLO]))["rg_economico"] == "ok"
