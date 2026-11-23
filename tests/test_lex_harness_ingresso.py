"""Ingresso dell'harness allargato (23/11/2026): le domande giuridiche formulate liberamente entrano anche senza le formule
di parere dell'elenco, purché riguardino un istituto giuridico o descrivano una fattispecie riconosciuta; le richieste sui
dati dello studio restano operative. Frasi nuove, diverse dal catalogo di copertura e dai banchi."""
from __future__ import annotations

import pytest

from lex.harness.comprensione import comprendi

GIURIDICHE = [
    "Il curatore può sciogliersi dal contratto preliminare di vendita?",
    "Usucapione di una striscia di terreno del vicino: quanti anni servono?",
    "Il socio accomandante risponde dei debiti della società?",
    "Revocazione per errore di fatto: entro quando?",
    "Prepara un'istanza di sospensione dell'esecuzione al giudice dell'esecuzione.",
    "Il fideiussore può opporre al creditore le eccezioni del debitore principale?",
    "La banca ci ha addebitato interessi oltre la soglia: è usura?",
]
OPERATIVE = ["cosa devo fare oggi?", "che udienze ho domani?", "mostrami le scadenze della settimana",
             "quali PEC sono arrivate stamattina?", "elenca i fascicoli del cliente Rossi"]


@pytest.mark.parametrize("frase", GIURIDICHE)
def test_domande_giuridiche_entrano(frase):
    assert comprendi(frase).per_harness, comprendi(frase)


@pytest.mark.parametrize("frase", OPERATIVE)
def test_richieste_operative_restano_fuori(frase):
    assert not comprendi(frase).per_harness
