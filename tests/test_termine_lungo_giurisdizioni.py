"""Termine lungo della sentenza per giurisdizione (direttiva del 01/11/2026: tutte le materie)."""

from datetime import date
from types import SimpleNamespace

import pytest

from pct.termine_lungo_sentenza import azione_e_norma, giurisdizione, proponi_termine_lungo


@pytest.mark.parametrize("testo, attesa, azione, norma", [
    ("Tribunale di Locri, sentenza n. 5/2026 depositata il 01/10/2026", "civile", "Appello", "art. 327 c.p.c."),
    ("Corte d'Appello di Reggio Calabria, sentenza n. 9/2026", "civile", "Ricorso per cassazione", "art. 327 c.p.c."),
    ("TRIBUNALE AMMINISTRATIVO REGIONALE PER LA CALABRIA sentenza n. 345/2026", "amministrativo",
     "Appello al Consiglio di Stato", "art. 92, c. 3, c.p.a."),
    ("Corte di giustizia tributaria di primo grado di Reggio Calabria, sentenza n. 1200/2026", "tributario",
     "Appello alla Corte di giustizia tributaria di secondo grado", "art. 327 c.p.c. e art. 51 D.Lgs. 546/1992"),
])
def test_azione_e_norma_per_giurisdizione(testo, attesa, azione, norma):
    assert giurisdizione(testo) == attesa
    assert azione_e_norma(testo) == (azione, norma)


def test_la_sentenza_penale_non_riceve_il_termine_di_sei_mesi():
    testo = "Tribunale di Locri, sentenza n. 77/2026 depositata il 01/09/2026 nel procedimento penale a carico dell'imputato"
    assert giurisdizione(testo) == "penale"

    class Scadenziario:
        def tutte(self, **_):
            raise AssertionError("nessuna scadenza va cercata o creata per il penale")

    assert proponi_termine_lungo(Scadenziario(), fascicolo_id="F1", comunicazione_id="m1", testo=testo,
                                 pubblicazione=date(2026, 9, 1), lavoro=False, oggi=date(2026, 9, 2), origine="PEC") is False


def test_titolo_della_scadenza_amministrativa():
    creata = {}

    class Scadenziario:
        def tutte(self, **_):
            return []

        def nuova(self, **campi):
            creata.update(campi)
            return SimpleNamespace(id="S1")

        def aggiorna(self, *_args, **_campi):
            return None

    testo = "TRIBUNALE AMMINISTRATIVO REGIONALE PER LA CALABRIA sentenza n. 345/2026 pubblicata il 10/09/2026"
    assert proponi_termine_lungo(Scadenziario(), fascicolo_id="F1", comunicazione_id="m2", testo=testo,
                                 pubblicazione=date(2026, 9, 10), lavoro=False, oggi=date(2026, 9, 11), origine="PEC")
    assert creata["titolo"].startswith("Appello al Consiglio di Stato — termine lungo art. 92, c. 3, c.p.a.")
    assert "60 giorni" in creata["descrizione"]
