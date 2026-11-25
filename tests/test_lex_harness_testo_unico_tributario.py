"""Processo tributario: d.lgs. 546/1992 fino al 31/12/2026, testo unico della giustizia tributaria (d.lgs. 175/2024) dal
1° gennaio 2027 (artt. 130 e 131 del testo unico, testo vigente al 24/11/2026). Frasi nuove (24/11/2026)."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.norme import ISTANTANEA
from lex.harness.vigenza_tributaria import TAVOLA, _testo

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

DOMANDA = ("Al mio cliente l'Agenzia delle entrate ha notificato il {d} un avviso di accertamento IRPEF. Entro quando "
           "presentiamo il ricorso tributario?")


def test_nel_2026_cita_il_546_e_avverte_del_testo_unico():
    r = rispondi(DOMANDA.format(d="20/11/2026") + "\n\nOggi è il 24/11/2026.", oggi=date(2026, 11, 24))
    assert r.regola == "ricorso_tributario"
    assert "art. 21 d.lgs. 546/1992" in r.testo
    assert "1° gennaio 2027" in r.testo and "art. 131 d.lgs. 175/2024" in r.testo
    assert not r.affermazioni_tolte and not r.citazioni_non_verificate


def test_dal_2027_cita_il_testo_unico():
    r = rispondi(DOMANDA.format(d="10/01/2027") + "\n\nOggi è il 15/01/2027.", oggi=date(2027, 1, 15))
    assert r.regola == "ricorso_tributario"
    assert "art. 67 d.lgs. 175/2024" in r.testo and "d.lgs. 546/1992" not in r.testo.split("**Avvertenze**")[0]
    assert not r.affermazioni_tolte and not r.citazioni_non_verificate


def test_tavola_dalle_rubriche_e_riscrittura_dei_testi():
    assert TAVOLA["21"] == "67" and TAVOLA["22"] == "68"
    assert _testo("ricorso (artt. 18 e 21 d.lgs. 546/1992)") == "ricorso (artt. 64 e 67 d.lgs. 175/2024)"
