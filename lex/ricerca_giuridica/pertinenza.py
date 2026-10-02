"""Pertinenza assoluta di un risultato rispetto alla domanda.

Il punteggio ibrido e' relativo (il primo risultato vale sempre 1): non basta a dire
se una fonte risponde davvero alla domanda. Qui si misura quanta parte dei termini
significativi della domanda compare nel testo del risultato.
"""

from __future__ import annotations

from .testo import analizza_domanda, termini_indice

SOGLIA_COPERTURA = 0.34


def copertura_termini(domanda: str, testo: str) -> float:
    termini = analizza_domanda(domanda, usa_tesauro=False).termini
    termini = [t for t in termini if not t.isdigit()]
    if not termini:
        return 1.0
    presenti = set(termini_indice(testo))
    return round(sum(1 for t in termini if t in presenti) / len(termini), 4)


def e_pertinente(domanda: str, testo: str, *, riferimento_esatto: bool = False, soglia: float = SOGLIA_COPERTURA) -> bool:
    if riferimento_esatto:
        return True
    return copertura_termini(domanda, testo) >= soglia


__all__ = ["SOGLIA_COPERTURA", "copertura_termini", "e_pertinente"]
