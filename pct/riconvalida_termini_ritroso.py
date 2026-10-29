"""Riconvalida delle memorie art. 171-ter c.p.c. salvate con il calcolo in avanti.

Fino alla versione 2.457.6 i preset dello scadenziario contavano 40, 20 e 10 giorni **dopo** l'udienza, mentre
l'art. 171-ter c.p.c. fissa le memorie «almeno quaranta / venti / dieci giorni prima dell'udienza». La
riconvalida ricalcola a ritroso solo le scadenze aperte che portano ancora la data prodotta dal vecchio
calcolo: una data modificata dall'avvocato non si tocca, riceve soltanto una nota da verificare.
La correzione è idempotente: una scadenza già corretta non soddisfa più le condizioni.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from pct.scadenziario import (
    PRESET_TERMINI,
    GestioneScadenziario,
    StatoTermine,
    calcola_termine,
    profilo_da_preset,
)

logger = logging.getLogger(__name__)

_PRESET_RITROSO = {key: preset for key, preset in PRESET_TERMINI.items() if preset.get("direzione") == "ritroso"}
_PROFILI_VECCHI = {preset["profile_code"].removesuffix("_BEFORE"): key for key, preset in _PRESET_RITROSO.items()}
NOTA_CORRETTA = "Data ricalcolata a ritroso dall'udienza (art. 171-ter c.p.c.): prima risultava il {vecchia}."
NOTA_DA_VERIFICARE = ("Verificare la data: la memoria art. 171-ter c.p.c. va depositata prima dell'udienza del {udienza} "
                      "(calcolo a ritroso: {nuova}).")


def _giorno(valore: Any) -> date | None:
    try:
        return date.fromisoformat(str(valore or "")[:10])
    except ValueError:
        return None


def _preset_della_scadenza(scadenza: Any) -> str:
    codice = str(getattr(scadenza, "deadline_profile_code", "") or "")
    testo = f"{getattr(scadenza, 'titolo', '')} {getattr(scadenza, 'descrizione', '')}".casefold()
    if codice in _PROFILI_VECCHI and "171" in testo and str(getattr(scadenza, "source_event_type", "")) == "udienza":
        return _PROFILI_VECCHI[codice]
    return ""


def riconvalida_memorie_171ter(scadenziario: GestioneScadenziario) -> dict[str, int]:
    """Corregge le memorie 171-ter aperte calcolate dopo l'udienza; restituisce i conteggi."""
    esito = {"corrette": 0, "da_verificare": 0}
    for scadenza in list(scadenziario.tutte(solo_aperte=False)):
        if getattr(scadenza, "stato", None) not in {StatoTermine.APERTO, StatoTermine.BOZZA, StatoTermine.SCADUTO}:
            continue
        chiave = _preset_della_scadenza(scadenza)
        udienza = _giorno(getattr(scadenza, "source_event_at", "") or getattr(scadenza, "data_decorrenza", ""))
        attuale = _giorno(getattr(scadenza, "data_scadenza", ""))
        if not chiave or udienza is None or attuale is None or attuale <= udienza:
            continue
        preset = PRESET_TERMINI[chiave]
        calcolo = GestioneScadenziario.calcola_avanzata(start_at=udienza, profile=profilo_da_preset(chiave))
        nuova = calcolo.legal_due_at[:10]
        vecchio_calcolo = calcola_termine(udienza, giorni=int(preset["giorni"]), tipo=preset.get("tipo", "liberi"),
                                          sospensione_feriale=bool(preset.get("sospensione_feriale", True)))
        legale_vecchio = _giorno(getattr(scadenza, "legal_due_at", ""))
        prodotta_dal_software = attuale == vecchio_calcolo or attuale == legale_vecchio
        vecchia = attuale.strftime("%d/%m/%Y")
        note = str(getattr(scadenza, "note", "") or "")
        try:
            if prodotta_dal_software:
                riga = NOTA_CORRETTA.format(vecchia=vecchia)
                scadenziario.aggiorna(
                    scadenza.id, data_scadenza=nuova, raw_due_at=calcolo.raw_due_at, legal_due_at=calcolo.legal_due_at,
                    deadline_profile_code=preset["profile_code"], note=f"{note}\n{riga}".strip(),
                )
                esito["corrette"] += 1
            else:
                riga = NOTA_DA_VERIFICARE.format(udienza=udienza.strftime("%d/%m/%Y"),
                                                 nuova=date.fromisoformat(nuova).strftime("%d/%m/%Y"))
                if riga not in note:
                    scadenziario.aggiorna(scadenza.id, note=f"{note}\n{riga}".strip())
                    esito["da_verificare"] += 1
        except Exception:  # una scadenza non aggiornabile non blocca le altre
            logger.exception("[riconvalida 171-ter] scadenza %s non aggiornata", getattr(scadenza, "id", ""))
    return esito


__all__ = ["riconvalida_memorie_171ter"]
