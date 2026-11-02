"""Gruppo (b): le norme dei termini e delle udienze aperte nel fascicolo.

Per ogni scadenza aperta la norma si ricava, in quest'ordine, da ciò che il
software ha già registrato: il modello di termine che l'ha calcolata
(`deadline_profile_code`, con la norma di `pct.termini_processuali` e
l'adempimento delle schede di rito che richiama lo stesso modello), la
modalità dell'udienza letta dal provvedimento (trattazione scritta = art.
127-ter c.p.c.) e le citazioni scritte nel titolo, nella descrizione o nelle
note. Una citazione presente nel registro delle fonti porta l'estratto; le
altre portano solo il collegamento ufficiale.
"""

from __future__ import annotations

import re
from typing import Any

from pct.procedura_fasi import SCHEDE_RITO
from pct.procedura_fasi.fonti import FONTI
from pct.procedura_fasi.lacune import articoli_citati, riferimenti_nel_testo

from .voci import aggiungi, data_italiana, voce_citazione, voce_registro

STATI_APERTI = {"APERTO", "APERTA", "IN_CORSO"}


def _chiave(testo: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(testo or "").lower().replace("artt.", "art.").replace("articolo", "art."))


def _registro_per_citazione() -> dict[str, str]:
    return {_chiave(voce["norma"]): identificativo for identificativo, voce in FONTI.items()}


def _fonti_per_modello() -> dict[str, list[str]]:
    """Il modello di termine → le fonti dell'adempimento che lo richiama nelle schede di rito."""
    indice: dict[str, list[str]] = {}
    for scheda in SCHEDE_RITO.values():
        for fase in scheda.get("fasi", []):
            for adempimento in fase.get("adempimenti", []):
                modello = str(adempimento.get("template") or "")
                if modello:
                    indice.setdefault(modello, []).extend(adempimento.get("fonti", []))
    return indice


def _norma_del_modello(codice: str) -> str:
    from pct.termini_processuali import DEFAULT_TEMPLATES

    modello = next((t for t in DEFAULT_TEMPLATES if t.code == codice), None)
    return str(getattr(modello, "reference_law", "") or "")


def _valore(scadenza: Any, campo: str) -> str:
    valore = scadenza.get(campo, "") if isinstance(scadenza, dict) else getattr(scadenza, campo, "")
    return " ".join(str(getattr(valore, "value", valore) or "").split())


def _motivo(scadenza: Any) -> str:
    titolo = _valore(scadenza, "titolo") or "Termine senza titolo"
    giorno = data_italiana(_valore(scadenza, "data_scadenza") or _valore(scadenza, "data"))
    tipo = "udienza" if _valore(scadenza, "tipo").upper() == "UDIENZA" else "termine aperto"
    return f"perché: {tipo} al {giorno} — «{titolo}»" if giorno else f"perché: {tipo} — «{titolo}»"


def norme_termini(scadenze: list[Any]) -> dict[str, Any]:
    registro = _registro_per_citazione()
    per_modello = _fonti_per_modello()
    voci: dict[str, dict[str, Any]] = {}
    aperte = [s for s in scadenze if _valore(s, "stato").upper() in STATI_APERTI]
    aperte.sort(key=lambda s: _valore(s, "data_scadenza") or _valore(s, "data") or "9999")
    for scadenza in aperte:
        motivo = _motivo(scadenza)
        codice = _valore(scadenza, "deadline_profile_code")
        for identificativo in per_modello.get(codice, []):
            aggiungi(voci, voce_registro(identificativo), motivo)
        if _valore(scadenza, "hearing_mode").lower() == "note_scritte":
            aggiungi(voci, voce_registro("cpc_127ter"), motivo)
        testo = " ".join(
            _valore(scadenza, campo) for campo in ("titolo", "descrizione", "note")
        ) + " " + _norma_del_modello(codice)
        for composta in riferimenti_nel_testo(testo):
            for citazione in articoli_citati(composta):
                identificativo = registro.get(_chiave(citazione))
                voce = voce_registro(identificativo) if identificativo else voce_citazione(citazione)
                aggiungi(voci, voce, motivo)
    if voci:
        vuoto = ""
    elif aperte:
        vuoto = "I termini aperti del fascicolo non indicano una norma registrata: la base del termine va annotata nella scadenza."
    else:
        vuoto = "Nessun termine o udienza aperti nel fascicolo."
    return {"voci": list(voci.values()), "termini": len(aperte), "vuoto": vuoto}


__all__ = ["STATI_APERTI", "norme_termini"]
