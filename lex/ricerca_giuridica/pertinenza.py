"""Pertinenza assoluta di un risultato rispetto alla domanda.

Il punteggio ibrido e' relativo (il primo risultato vale sempre 1): non basta a dire
se una fonte risponde davvero alla domanda. Qui si misura quanta parte dei termini
significativi della domanda compare nel testo del risultato.

Il legislatore spesso non usa le parole della dottrina: l'art. 2043 c.c. non dice mai
«responsabilita' extracontrattuale», dice «fatto doloso o colposo [...] danno ingiusto».
Per questo un termine della domanda conta come presente anche quando la voce del tesauro
che lo contiene compare nel testo con le parole della legge; e «termine» conta come
presente quando il testo indica una durata (giorni, mesi, anni).
"""

from __future__ import annotations

from .testo import analizza_domanda, corrispondenze_tesauro, termini_indice

SOGLIA_COPERTURA = 0.34

# Radici con cui una norma esprime una durata: coprono il termine «termine» della domanda.
_RADICI_DURATA = frozenset(termini_indice("giorni giorno mesi mese anni anno decorsi decorso ore"))
_RADICI_TERMINE = frozenset(termini_indice("termine termini"))


def copertura_termini(domanda: str, testo: str) -> float:
    termini = analizza_domanda(domanda, usa_tesauro=False).termini
    termini = [t for t in termini if not t.isdigit()]
    if not termini:
        return 1.0
    presenti = set(termini_indice(testo))
    coperti = {t for t in termini if t in presenti}
    for radici_voce, radici_legge in corrispondenze_tesauro(domanda):
        # Servono almeno meta' delle parole della legge (minimo due): una sola parola comune
        # («danno», «opposizione») non basta a dire che il testo parla di quell'istituto.
        distintive = radici_legge - radici_voce
        if distintive and len(presenti & distintive) >= max(min(2, len(distintive)), (len(distintive) + 1) // 2):
            coperti.update(t for t in termini if t in radici_voce)
    if presenti & _RADICI_DURATA:
        coperti.update(t for t in termini if t in _RADICI_TERMINE)
    return round(len(coperti) / len(termini), 4)


def e_pertinente(domanda: str, testo: str, *, riferimento_esatto: bool = False, soglia: float = SOGLIA_COPERTURA) -> bool:
    if riferimento_esatto:
        return True
    return copertura_termini(domanda, testo) >= soglia


__all__ = ["SOGLIA_COPERTURA", "copertura_termini", "e_pertinente"]
