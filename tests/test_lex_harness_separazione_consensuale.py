"""Separazione consensuale su domanda congiunta (art. 473-bis.51 c.p.c.), distinta dalla separazione giudiziale; nessun
lato della parte (i coniugi chiedono insieme). Frasi nuove, scritte per questo controllo (24/11/2026)."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.lato import famiglia
from lex.harness.norme import ISTANTANEA

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

OGGI = "\n\nOggi è il 24/11/2026."


def _r(t):
    return rispondi(t + OGGI, oggi=date(2026, 11, 24))


def test_con_figli_minori_ricorso_congiunto_e_niente_accordo_dal_sindaco():
    r = _r("Mia moglie e io vogliamo separarci d'accordo, abbiamo un figlio di 8 anni e viviamo a Treviso. Come facciamo "
           "una separazione consensuale?")
    assert r.regola == "separazione_consensuale"
    assert "art. 473-bis.51 c.p.c." in r.testo and "art. 158 c.c." in r.testo
    assert "residenza abituale" in r.testo and "dieci giorni al procuratore" in r.testo
    assert "sindaco come ufficiale" not in r.testo.split("**Come e perché**")[0]
    assert not r.affermazioni_tolte and not r.citazioni_non_verificate


def test_senza_figli_anche_l_accordo_davanti_al_sindaco():
    r = _r("Il mio cliente e la moglie, senza figli, sono d'accordo su tutto e vogliono separarsi in modo consensuale: qual "
           "è la strada più semplice?")
    assert r.regola == "separazione_consensuale"
    assert "art. 12 d.l. 132/2014" in r.testo and "trasferimento patrimoniale" in r.testo


def test_coniuge_contrario_resta_alla_separazione_giudiziale():
    assert _r("Mio marito vuole separarsi ma io non sono d'accordo: come funziona la separazione?").regola == "separazione_giudiziale"


def test_negoziazione_chiesta_resta_alla_negoziazione_familiare():
    r = _r("Due coniugi d'accordo vogliono separarsi con la negoziazione assistita, senza figli: come si procede?")
    assert r.regola == "negoziazione_familiare"


def test_la_separazione_consensuale_non_ha_lato():
    assert famiglia("separazione_consensuale") is None
