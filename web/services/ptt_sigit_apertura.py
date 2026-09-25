"""Procedimento tributario telematico (PTT) impostato già all'apertura del fascicolo.

Nella creazione del fascicolo tributario (completa o «Fascicolo Veloce»)
l'avvocato indica subito i dati che la nota di iscrizione a ruolo chiede e che
fanno partire i termini: Corte di giustizia tributaria, posizione, atto
impugnato con numero, data di notifica e valore della lite, data di notifica
del ricorso (da cui decorrono i 30 giorni per costituirsi, art. 22 D.Lgs.
546/1992), numero di ruolo se il ricorso è già iscritto. Il fascicolo resta
salvato anche se questa parte non va a buon fine: si completa dalla sezione
«Deposito tributario (PTT)».
"""

from __future__ import annotations

from typing import Any, Mapping

from flask import current_app

from pct.ptt_sigit import catalogo, cut
from web.services import ptt_sigit_azioni as azioni

CAMPI = ("ptt_corte", "ptt_posizione", "ptt_rg", "ptt_notifica_ricorso", "ptt_atto_tipo", "ptt_atto_numero",
         "ptt_atto_notifica", "ptt_atto_ufficio", "ptt_valore", "ptt_periodo", "ptt_pubblica_udienza")


def catalogo_apertura(ufficio: str = "") -> dict[str, Any]:
    dati = catalogo.catalogo()
    esito: dict[str, Any] = {"ok": True, "sedi": dati["sedi"], "attiImpugnati": dati["attiImpugnati"],
                             "pubblicaUdienza": dati["pubblicaUdienza"], "posizioni": ["ricorrente", "resistente"],
                             "scaglioni": [{"fino": s, "cut": c} for s, c in cut.SCAGLIONI] + [{"fino": None, "cut": cut.MASSIMO}]}
    if ufficio.strip():
        codice = catalogo.sede_da_testo(ufficio)
        esito["corte"] = catalogo.sede(codice) if codice else None
    return esito


def applica(fid: str, form: Mapping[str, Any]) -> str:
    """Salva i campi ``ptt_*`` del modulo; restituisce il messaggio per l'avvocato."""
    valori = {c: str(form.get(c) or "").strip() for c in CAMPI}
    if not any(valori.values()):
        return ""
    dati: dict[str, Any] = {}
    for campo, chiave in (("ptt_corte", "corte"), ("ptt_posizione", "posizione"), ("ptt_rg", "rg"),
                          ("ptt_notifica_ricorso", "notificaRicorso"), ("ptt_pubblica_udienza", "pubblicaUdienza")):
        if valori[campo]:
            dati[chiave] = valori[campo]
    if any(valori[c] for c in ("ptt_atto_tipo", "ptt_atto_numero", "ptt_atto_notifica", "ptt_valore")):
        dati["atti"] = [{"tipo": valori["ptt_atto_tipo"], "numero": valori["ptt_atto_numero"], "ufficio": valori["ptt_atto_ufficio"],
                         "dataNotifica": valori["ptt_atto_notifica"], "tributo": valori["ptt_valore"], "periodo": valori["ptt_periodo"]}]
    try:
        azioni.salva_procedimento(fid, dati)
        return " Procedimento tributario (PTT) impostato: prosegui dalla sezione «Deposito tributario»."
    except Exception as exc:
        current_app.logger.warning("Procedimento PTT non impostato all'apertura di %s: %s", fid, exc)
        return f" Procedimento tributario (PTT) da completare nella sezione «Deposito tributario»: {exc}"


__all__ = ["CAMPI", "applica", "catalogo_apertura"]
