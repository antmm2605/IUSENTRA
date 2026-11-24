"""Strumenti vicini che si confondevano (24/11/2026): frasi nuove, mai i banchi."""
from __future__ import annotations

import pytest

from lex.harness import rispondi

CASI = [
    ("Divorziati con sentenza del 2022: l'ex vuole abbassare l'assegno per la figlia perché guadagna meno", "modifica_condizioni"),
    ("Per recuperare 18.000 euro prestati a un amico dobbiamo fare un passaggio obbligatorio prima di andare dal giudice?",
     "negoziazione_obbligatoria"),
    ("Il decreto ingiuntivo era stato notificato al vecchio indirizzo, non abbiamo mai ricevuto nulla e ora ci pignorano il conto",
     "mon_opposizione_tardiva"),
    ("Vorrei presentare ricorso al prefetto contro la contravvenzione per divieto di sosta", "cds_prefetto"),
]


@pytest.mark.parametrize("domanda,regola", CASI)
def test_strumenti_vicini_distinti(domanda, regola):
    r = rispondi(domanda)
    assert r is not None and r.regola == regola, r.regola if r else None
