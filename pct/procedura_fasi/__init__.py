"""Conoscenza procedurale versionata: fasi, termini e norme dei depositi, delle notifiche e dei riti.

Il software gestisce già i depositi (PCT, PDP, PAT, PTT) e le notifiche (PEC in
proprio, UNEP, posta, cancelleria) con le loro macchine a stati; questo
pacchetto aggiunge la parte che l'avvocato deve sapere per decidere: in quale
fase si è, che cosa la prova, quanto tempo c'è e quale norma lo dice. Ogni voce
cita una fonte del registro `fonti.py`, verificata alla data indicata; i termini
richiamano, dove esistono, i template del motore `pct/termini_processuali.py`.

Nulla di questo tocca la logica esistente: le schede leggono gli stati, non
li cambiano.
"""

from __future__ import annotations

from typing import Any

from .depositi import SCHEDE_DEPOSITO, canale_deposito, fase_deposito, scheda_deposito
from .fonti import FONTI, fonte, fonti, norme
from .lacune import lacune_conoscenza, riferimenti_nel_testo
from .notifiche import SCHEDE_NOTIFICA, canale_notifica, fase_notifica, scheda_notifica
from .riti import SCHEDE_RITO, rito_per_fascicolo, scheda_rito

VERSIONE_CONOSCENZA = "2026.09.14.fasi-procedurali.v1"


def _con_fonti(scheda: dict[str, Any]) -> dict[str, Any]:
    """La scheda con l'elenco delle fonti citate, pronta per l'interfaccia."""
    if not scheda:
        return {}
    identificativi: list[str] = []
    for fase in scheda.get("fasi", []):
        identificativi.extend(fase.get("fonti", []))
        for adempimento in fase.get("adempimenti", []):
            identificativi.extend(adempimento.get("fonti", []))
    for voce in scheda.get("tempistiche", []):
        identificativi.extend(voce.get("fonti", []))
    return {**scheda, "fonti": fonti(identificativi), "versione": VERSIONE_CONOSCENZA}


def schede_per_fascicolo(
    *,
    tipo: str = "",
    tipo_procedimento: str = "",
    canale_operativo: str = "",
    canali_notifica: list[str] | tuple[str, ...] = (),
) -> dict[str, Any]:
    """Le schede pertinenti a un fascicolo: rito, canale di deposito, canali di notifica usati."""
    rito = rito_per_fascicolo(tipo, tipo_procedimento)
    canale = canale_deposito(canale_operativo) or {
        "PENALE": "PDP_PENALE", "AMMINISTRATIVO": "PAT_AMMINISTRATIVO", "TRIBUTARIO": "PTT_TRIBUTARIO",
    }.get(" ".join(str(tipo or "").split()).upper(), "PCT_TELEMATICO")
    notifiche = []
    visti: set[str] = set()
    for valore in list(canali_notifica) + ["pec"]:
        codice = canale_notifica(valore)
        if codice and codice not in visti:
            visti.add(codice)
            notifiche.append(_con_fonti(scheda_notifica(codice)))
    return {
        "versione": VERSIONE_CONOSCENZA,
        "rito": _con_fonti(scheda_rito(rito)),
        "deposito": _con_fonti(scheda_deposito(canale)),
        "notifiche": notifiche,
    }


__all__ = [
    "FONTI", "SCHEDE_DEPOSITO", "SCHEDE_NOTIFICA", "SCHEDE_RITO", "VERSIONE_CONOSCENZA",
    "canale_deposito", "canale_notifica", "fase_deposito", "fase_notifica", "fonte", "fonti", "lacune_conoscenza", "norme", "riferimenti_nel_testo",
    "rito_per_fascicolo", "scheda_deposito", "scheda_notifica", "scheda_rito", "schede_per_fascicolo",
]
