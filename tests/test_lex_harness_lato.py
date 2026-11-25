"""Lato della parte assistita (24/11/2026): chi subisce non riceve lo strumento di chi agisce; se il lato è ignoto e la
domanda è generica, Lex chiede. Frasi nuove, mai i banchi."""
from __future__ import annotations

import pytest

from lex.harness import rispondi
from lex.harness.lato import ATTIVO, PASSIVO, lato_della_parte

OGGI = "\n\nOggi è il 24/11/2026."


@pytest.mark.parametrize("testo,lato", [
    ("Mi hanno notificato un decreto ingiuntivo per 8.000 euro", PASSIVO),
    ("Il debitore non mi paga le fatture da mesi", ATTIVO),
    ("Ho ricevuto un precetto dalla banca", PASSIVO),
    ("Vogliamo pignorare il conto del debitore", ATTIVO),
    ("Hanno pignorato l'auto che è di mia proprietà, non del debitore", PASSIVO),
    ("Decreto ingiuntivo da 5.000 euro", None),
])
def test_lato_letto_dal_testo(testo, lato):
    assert lato_della_parte(testo) == lato


@pytest.mark.parametrize("domanda,regole", [
    ("Al mio cliente è arrivato un decreto ingiuntivo da 12.000 euro del Tribunale di Asti, notificato il 10/11/2026: "
     "cosa possiamo fare?", {"opposizione_decreto_ingiuntivo", "mon_opposizione_tardiva", "mon_opposizione_di"}),
    ("Ci hanno notificato un precetto di 6.500 euro il 18/11/2026 ma il debito era già prescritto: come procediamo?",
     {"opposizione_precetto", "es_opposizione_esecuzione", "opposizione_atti_esecutivi"}),
])
def test_chi_subisce_riceve_lo_strumento_di_difesa(domanda, regole):
    r = rispondi(domanda + OGGI)
    assert r is not None and r.regola in regole, r.regola if r else None


def test_lato_ignoto_e_domanda_generica_chiede():
    r = rispondi("Decreto ingiuntivo da 5.000 euro del Tribunale di Pavia: cosa facciamo?" + OGGI)
    assert r is not None and r.regola == "chiarimento_lato"
    assert len(r.registro["scelte"]) == 2 and "creditore" in r.registro["scelte"][0] and "debitore" in r.registro["scelte"][1]
    assert lato_della_parte(r.registro["scelte"][0]) == ATTIVO and lato_della_parte(r.registro["scelte"][1]) == PASSIVO
