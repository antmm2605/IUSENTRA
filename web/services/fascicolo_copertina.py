"""Dati leggibili della copertina del fascicolo (stampa).

La copertina riporta i dati della pratica come li vede l'avvocato: stato e tipo in italiano, titolare
della pratica (in mancanza del referente, l'avvocato titolare dello studio, come in Anagrafica) e
l'udienza con l'etichetta onesta — «Prossima udienza» solo se la data non è ancora passata nel giorno
di Roma, altrimenti «Ultima udienza».
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

ROME_TZ = ZoneInfo("Europe/Rome")

_STATI = {
    "APERTO": "Aperto",
    "IN_CORSO": "In corso",
    "SOSPESO": "Sospeso",
    "DEFINITO": "Definito",
    "ARCHIVIATO": "Archiviato",
}
_TIPI = {
    "CIVILE": "Civile",
    "PENALE": "Penale",
    "AMMINISTRATIVO": "Amministrativo",
    "TRIBUTARIO": "Tributario",
    "STRAGIUDIZIALE": "Stragiudiziale",
    "CONSULENZA": "Consulenza",
    "LAVORO": "Lavoro",
    "FAMIGLIA": "Famiglia",
    "SUCCESSIONI": "Successioni",
    "ALTRO": "Altro",
}


def _chiave(valore: Any) -> str:
    return str(getattr(valore, "value", valore) or "").strip().upper()


def _leggibile(chiave: str) -> str:
    parole = chiave.replace("_", " ").lower()
    return parole[:1].upper() + parole[1:]


def _data(valore: Any) -> date | None:
    testo = str(valore or "").strip()
    if not testo:
        return None
    try:
        return datetime.fromisoformat(testo[:10]).date()
    except ValueError:
        pass
    try:
        return datetime.strptime(testo[:10], "%d/%m/%Y").date()
    except ValueError:
        return None


def contesto_copertina(fascicolo: Any, avvocato_studio: str = "", oggi: date | None = None) -> dict[str, Any]:
    """Valori della copertina; mai chiavi tecniche, mai una data passata come «prossima»."""
    stato = _chiave(getattr(fascicolo, "stato", ""))
    tipo = _chiave(getattr(fascicolo, "tipo", ""))
    titolare = str(getattr(fascicolo, "avvocato_referente", "") or "").strip() or str(avvocato_studio or "").strip()
    giorno = oggi or datetime.now(ROME_TZ).date()
    udienza = _data(getattr(fascicolo, "data_prossima_udienza", ""))
    return {
        "stato_label": _STATI.get(stato) or _leggibile(stato),
        "tipo_label": _TIPI.get(tipo) or _leggibile(tipo),
        "titolare": titolare,
        "udienza_label": "Ultima udienza" if udienza and udienza < giorno else "Prossima udienza",
    }
