"""Impugnazione senza materia: Lex chiede se il procedimento è civile o penale invece di indovinare (23/11/2026)."""
from __future__ import annotations

import pytest

from lex.harness import rispondi
from lex.harness.chiarimenti import materia_da_chiarire

AMBIGUE = ["La sentenza di condanna è stata depositata: entro quanto proponiamo appello?",
           "Prepara il ricorso per cassazione per vizio di motivazione.",
           "La sentenza ci dà torto: possiamo impugnarla e in che tempi?",
           "Quali motivi si possono far valere con il ricorso per cassazione?"]
CHIARE = ["La sentenza di condanna per furto è stata depositata ieri: entro quanto proponiamo appello?",
          "Il tribunale civile ha respinto la domanda di risarcimento: entro quando appelliamo?",
          "La Corte d'appello ha confermato la condanna dell'imputato: ricorso per cassazione?",
          "Appello contro la sentenza del giudice di pace sul sinistro: termine?"]


@pytest.mark.parametrize("domanda", AMBIGUE)
def test_impugnazione_senza_materia_chiede_civile_o_penale(domanda):
    r = rispondi(domanda)
    assert r is not None and r.regola == "chiarimento_materia" and r.tipo == "chiarimento"
    scelte = r.registro["scelte"]
    assert len(scelte) == 2 and scelte[0].endswith("(procedimento civile)") and scelte[1].endswith("(procedimento penale)")
    assert "civile o penale" in r.testo and scelte[0] in r.testo and scelte[1] in r.testo
    assert r.to_dict()["choices"] == scelte


@pytest.mark.parametrize("domanda", CHIARE)
def test_con_la_materia_indicata_non_chiede(domanda):
    assert materia_da_chiarire(domanda) is None


def test_la_scelta_rimandata_porta_alla_materia_giusta():
    civile, penale = materia_da_chiarire(AMBIGUE[0])
    assert materia_da_chiarire(civile) is None and materia_da_chiarire(penale) is None
    r = rispondi(penale)
    assert r is not None and r.regola != "chiarimento_materia" and not r.regola.startswith("civ_")
