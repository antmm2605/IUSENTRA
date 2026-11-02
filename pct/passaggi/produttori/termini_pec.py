"""Adattatore: i termini che il presidio PEC propone (già attivo) come passaggi spiegabili.

Il presidio PEC (``pct/pec_pipeline.py`` con ``pct/pec_legal_deadline_proposer.py``)
legge la comunicazione, riconosce la norma, calcola la scadenza con il motore
dei termini e la propone; la Lettura del fascicolo la espone in
``pec.termini_da_registrare`` (``pct/fascicolo_lettura/pec.py``). Qui ogni
termine non ancora registrato diventa un passaggio: regola = norma citata,
prova = la PEC, dati = decorrenza, campo = scadenza calcolata (vincolata: la
calcola il motore dalla norma). Un termine perentorio porta il vincolo
omonimo: l'avvocato può chiedere di essere sempre interpellato, non può
far sparire il termine.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from pct.procedura_fasi.fonti import FONTI

from ..modello import Campo, Contesto, Dato, Passaggio, Prova

PRODUTTORE = "presidio PEC"
PREFISSO_REGOLA = "pec.termine."


def _compatta(testo: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(testo or "").lower())


_NORME_PER_TESTO = {_compatta(voce.get("norma")): chiave for chiave, voce in FONTI.items()}


def regola_del_termine(termine: dict[str, Any]) -> str:
    """Identificativo stabile della regola: la norma citata, altrimenti il tipo di termine."""
    base = re.sub(r"[^a-z0-9]+", "_", str(termine.get("norma") or termine.get("tipo") or "non_specificato").lower()).strip("_")
    return PREFISSO_REGOLA + (base or "non_specificato")


def _iso(data_it: str) -> str:
    trovata = re.match(r"(\d{2})/(\d{2})/(\d{4})$", str(data_it or ""))
    return f"{trovata.group(3)}-{trovata.group(2)}-{trovata.group(1)}" if trovata else str(data_it or "")


def passaggi_termini_pec(termini: Iterable[dict[str, Any]], contesto: Contesto) -> list[Passaggio]:
    passaggi: list[Passaggio] = []
    for numero, termine in enumerate(termini):
        norma = str(termine.get("norma") or "")
        fonte = _NORME_PER_TESTO.get(_compatta(norma))
        regola = regola_del_termine(termine)
        oggetto = str(termine.get("id") or f"{termine.get('messaggio_id')}:{numero}")
        scadenza = str(termine.get("scadenza") or "")
        tipo = str(termine.get("tipo") or "termine")
        perentorio = bool(termine.get("perentorio"))
        campi = {"scadenza": Campo("Scadenza calcolata", _iso(scadenza), vincolato=True,
                                   motivo_vincolo="la calcola il motore dei termini dalla norma e dalla decorrenza")} if scadenza else {}
        passaggi.append(Passaggio(
            chiave=f"{regola}:{contesto.fascicolo_id}:{oggetto}", produttore=PRODUTTORE, ordine=100 + numero,
            titolo=f"Proposto il termine «{tipo}»" + (f" entro il {scadenza}" if scadenza else " (scadenza da verificare)"),
            stato="da_confermare" if termine.get("da_rivedere") or not scadenza else "proposto",
            regola_id=regola,
            regola_descrizione=f"La comunicazione cita {norma or 'un termine'}: il presidio calcola la scadenza dalla decorrenza "
                               "con il motore deterministico dei termini e la propone senza registrarla da sola.",
            contesto=contesto, norme=(fonte,) if fonte else ("cpc_136",),
            prove=(Prova("pec", str(termine.get("oggetto") or ""), f"PEC del {termine.get('data_pec') or ''}".strip(),
                         str(termine.get("messaggio_id") or "")),),
            dati=tuple(d for d in (Dato("Decorrenza", str(termine.get("decorrenza") or ""), "data della comunicazione"),
                                   Dato("Norma citata", norma, "testo della PEC")) if d.valore),
            campi=campi, vincoli=("termine_perentorio",) if perentorio else (), href="#comunicazioni-notifica",
        ))
    return passaggi


__all__ = ["PREFISSO_REGOLA", "PRODUTTORE", "passaggi_termini_pec", "regola_del_termine"]
