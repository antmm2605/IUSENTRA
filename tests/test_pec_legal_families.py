from __future__ import annotations

import pytest

from pct.pec_legal_workflow import _classifica_famiglia


@pytest.mark.parametrize("testo, atteso", [
    ("Comunicazione del giudice delegato nella liquidazione giudiziale, curatore nominato", "procedure_concorsuali"),
    ("Avviso di vendita all'asta nell'esecuzione immobiliare, custode giudiziario", "esecuzione"),
    ("Tribunale per i minorenni: affidamento dei figli e responsabilita' genitoriale", "famiglia_minori"),
    ("Comunicazione del Tribunale Amministrativo Regionale (processo amministrativo telematico)", "comunicazione_pat"),
    ("Corte di giustizia tributaria, deposito SIGIT", "comunicazione_ptt_sigit"),
    # regressioni: le famiglie preesistenti restano
    ("Comunicazione di cancelleria, deposito sentenza", "comunicazione_cancelleria_civile"),
    ("Sistema di interscambio SDI fattura", "fattura_sdi"),
])
def test_classificazione_famiglie(testo, atteso):
    family, _ = _classifica_famiglia(testo, "", [])
    assert family == atteso
