"""Instradamento: redazioni, pareri e termini giuridici prima delle ricerche operative; le domande operative restano tali."""
from __future__ import annotations

from pathlib import Path

import pytest

from lex.harness.comprensione import comprendi, e_richiesta_giuridica
from lex.operational_knowledge.query_router import OperationalQueryRouter

FERRANDINA = (Path(__file__).parent / "lex_collaudo" / "ferrandina.txt").read_text(encoding="utf-8").strip()

GIURIDICHE = [
    FERRANDINA,
    # Varianti della stessa richiesta: verbo in mezzo, «oggi», «PEC», «termine», «parte» dentro il racconto.
    FERRANDINA.replace("Redigimi l'atto di citazione", "Mi serve che tu scriva l'atto di citazione"),
    "Oggi il cliente mi ha mandato una PEC: il venditore non si è presentato al rogito, abbiamo versato una caparra "
    "confirmatoria di 20.000 euro con il preliminare del 10/01/2026 e il termine della diffida è scaduto il 30/09/2026. "
    "Prepara l'atto di citazione per ottenere il doppio della caparra.",
    "Parte assistita: Rossi Mario (attore). Controparte: Verdi Luca. Termine scaduto ieri, PEC ricevuta oggi. "
    "Valuta rito e giudice per la domanda di pagamento di 12.000 euro: quale giudice è competente?",
    "Redigi un ricorso per decreto ingiuntivo per una fattura di 8.000 euro",
    "Scrivimi una comparsa di costituzione e risposta",
    "La negoziazione assistita è obbligatoria per una domanda di pagamento di 50.000 euro? Indica la norma.",
    "Qual è il termine per proporre appello contro una sentenza del Tribunale notificata il 20/04/2026?",
    "Cosa prevede l'art. 1385 del codice civile sulla caparra confirmatoria?",
    "Entro quando devo impugnare un licenziamento comunicato il 05/10/2026?",
]

OPERATIVE = [
    ("Cosa scade oggi?", "deadlines_overview"),
    ("PEC di oggi", None),
    ("Mostrami le udienze di domani", None),
    ("Quali scadenze ho questa settimana?", "calendar_query_page"),
    ("quali pec ricevute oggi generano scadenze", "pec_control_tower"),
    ("Dammi la situazione del cliente Bianchi", "client_situation"),
    ("scrivi una pec al cliente Rossi", "draft_communication"),
]


@pytest.mark.parametrize("domanda", GIURIDICHE)
def test_richieste_giuridiche_riconosciute_prima_delle_ricerche_operative(domanda):
    assert comprendi(domanda).per_harness, comprendi(domanda)
    assert OperationalQueryRouter().route(domanda) is None


def test_ferrandina_e_una_redazione_di_citazione():
    c = comprendi(FERRANDINA)
    assert (c.tipo, c.atto, c.racconto) == ("redazione", "atto di citazione", True)


@pytest.mark.parametrize("domanda,rotta", OPERATIVE)
def test_domande_operative_restano_operative(domanda, rotta):
    assert not e_richiesta_giuridica(domanda)
    route = OperationalQueryRouter().route(domanda)
    if rotta:
        assert route is not None and route.intent == rotta


def test_comunicazione_allegati_e_pec_non_cambiano():
    from lex.http_bounded_bridge import _is_communication_lookup

    assert _is_communication_lookup("verifica la firma della pec di deposito", {}, {})
    assert not _is_communication_lookup(FERRANDINA, {}, {})
