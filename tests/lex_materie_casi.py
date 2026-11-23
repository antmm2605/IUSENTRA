"""Verifica comune delle regole per materia dell'harness (fattispecie/materia_*.py).

Per ogni frase: la regola scelta deve essere quella attesa e la risposta deve uscire senza affermazioni tolte e senza
riferimenti non verificati. Se il passo d'ingresso (comprensione) non lascia ancora passare la frase, la si porta
all'harness come parere: l'ingresso è corretto a parte (lex/harness/comprensione.py) e qui si collauda la regola.
"""
from __future__ import annotations

import os

os.environ.setdefault("LEX_HARNESS_GIURISPRUDENZA", "0")
os.environ.setdefault("LEX_HARNESS_ARCHIVIO_VIVO", "0")


def risposta(frase: str):
    from lex.harness import rispondi
    from lex.harness.comprensione import Comprensione, atto_richiesto, comprendi

    c = comprendi(frase)
    if not c.per_harness or c.tipo == "norma":
        c = Comprensione("parere", c.atto or atto_richiesto(frase), c.racconto, True, ["collaudo della regola"])
    return rispondi(frase, comprensione=c)


# Strumenti coperti anche dalle regole di fattispecie/pubblico.py ed esecuzione.py (branch lex-regole): a parità di
# punteggio vince la regola che viene prima nell'elenco; entrambe sono risposte corrette sullo stesso strumento.
EQUIVALENTI = {
    "pi_differenze_retributive": {"ricorso_dipendente_pubblico"}, "pi_competenza": {"ricorso_dipendente_pubblico"},
    "pi_esecuzione_pa": {"esecuzione_contro_pa", "ottemperanza"}, "prev_ricorso_amministrativo": {"ricorso_amministrativo_inps"},
    "prev_ricorso_giudiziale": {"ricorso_442"}, "es_pignoramento_terzi": {"pignoramento_terzi"}, "es_ricerca_beni": {"ricerca_beni"},
}


def controlla(frase: str, regola: str) -> None:
    r = risposta(frase)
    assert r is not None, f"nessuna regola per: {frase}"
    assert r.regola == regola or r.regola in EQUIVALENTI.get(regola, set()), f"{frase} → {r.regola} (attesa {regola})"
    assert not r.affermazioni_tolte, r.affermazioni_tolte
    assert not r.citazioni_non_verificate, r.citazioni_non_verificate
