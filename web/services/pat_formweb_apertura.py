"""Procedimento amministrativo telematico (PAT) impostato già all'apertura del fascicolo.

Nella creazione del fascicolo amministrativo (completa o «Fascicolo Veloce»)
l'avvocato può indicare subito i dati che la creazione della bozza nel Formweb
chiede: sede (TAR, Consiglio di Stato, CGARS), tipo di ricorso, NRG se il
ricorso è già iscritto, posizione dell'assistito, contributo unificato. Il
fascicolo resta salvato anche se questa parte non va a buon fine: si completa
dalla sezione «Deposito amministrativo (PAT)».
"""

from __future__ import annotations

from typing import Any, Mapping

from flask import current_app

from pct.pat_formweb import catalogo
from web.services import pat_formweb_azioni as azioni
from web.services import pat_formweb_contesto as contesto

CAMPI = ("pat_sede", "pat_tipo_ricorso", "pat_nrg", "pat_posizione", "pat_cu", "pat_valore")
_MAPPA = {"pat_sede": "sede", "pat_tipo_ricorso": "tipoRicorso", "pat_nrg": "nrg", "pat_posizione": "posizione",
          "pat_cu": "cuTipologia", "pat_valore": "valore"}


def catalogo_apertura(ufficio: str = "") -> dict[str, Any]:
    """Le scelte della maschera di apertura e, se c'è l'ufficio del fascicolo, la sede come la scrive il portale."""
    dati = catalogo.catalogo()
    esito: dict[str, Any] = {"ok": True, "sedi": dati["sedi"], "tipiRicorsoTar": dati["tipiRicorsoTar"],
                             "tipiRicorsoCds": dati["tipiRicorsoCds"], "contributo": dati["contributo"],
                             "posizioni": ["ricorrente", "resistente", "controinteressato", "interveniente"]}
    if ufficio.strip():
        codice = contesto.sede_da_ufficio(ufficio)
        esito["sede"] = {"codice": codice, "descrizione": next((e for c, e in catalogo.SEDI.values() if c == codice), ""),
                         "ambito": catalogo.ambito(codice)}
    return esito


def applica(fid: str, form: Mapping[str, Any]) -> str:
    """Salva i campi ``pat_*`` del modulo; restituisce il messaggio per l'avvocato."""
    dati = {_MAPPA[c]: str(form.get(c) or "").strip() for c in CAMPI if str(form.get(c) or "").strip()}
    if not dati:
        return ""
    try:
        azioni.salva_procedimento(fid, dati)
        return " Procedimento amministrativo (PAT) impostato: prosegui dalla sezione «Deposito amministrativo»."
    except Exception as exc:
        current_app.logger.warning("Procedimento PAT non impostato all'apertura di %s: %s", fid, exc)
        return f" Procedimento amministrativo (PAT) da completare nella sezione «Deposito amministrativo»: {exc}"


__all__ = ["CAMPI", "applica", "catalogo_apertura"]
