"""Ricerca per significato e domanda di precisazione sullo strumento (24/11/2026). Frasi nuove, mai i banchi."""
from __future__ import annotations

import pytest

from lex.harness import rispondi
from lex.harness.significato import cerca, strumento_indicato


@pytest.mark.parametrize("frase,regola", [
    ("la banca mi ha messo in centrale rischi senza avvisarmi", "ban_segnalazione_centrale_rischi"),
    ("il socio di minoranza vuole uscire dalla srl e farsi liquidare la quota", "soc_recesso_socio"),
    ("mio zio e morto pieno di debiti e non voglio l eredita", "suc_rinuncia_eredita"),
])
def test_la_ricerca_trova_lo_strumento_anche_in_parole_comuni(frase, regola):
    assert cerca(frase, 1)[0][0].regola == regola


def test_fuori_materia_sotto_soglia():
    from lex.harness import SOGLIA_SIGNIFICATO

    assert cerca("che tempo fara domani a Roma", 1)[0][1] < SOGLIA_SIGNIFICATO


def test_la_scelta_rimandata_porta_allo_strumento():
    v = cerca("la banca mi ha messo in centrale rischi", 1)[0][0]
    domanda = f"la banca mi ha messo in centrale rischi (strumento: {v.nome})"
    assert strumento_indicato(domanda) == v.regola
    r = rispondi(domanda)
    assert r is not None and r.regola == v.regola


def test_linguaggio_comune_entra_e_propone_gli_strumenti():
    r = rispondi("il vicino ha alzato un muro sul confine e mi toglie la luce del giardino")
    assert r is not None and r.regola in {"chiarimento_strumento"} or (r is not None and r.regola.startswith(("pos_", "dr_")))


def test_domanda_vaga_chiede_i_fatti_o_propone():
    r = rispondi("ho un problema con un contratto, mi aiuti?")
    assert r is not None and r.regola in {"chiarimento_strumento", "fuori_materia"}
    assert "Serve una precisazione" in r.testo


@pytest.mark.parametrize("testo", ["buongiorno, a che ora apre lo studio?", "grazie mille", "mostrami le scadenze di domani"])
def test_saluti_e_operativi_non_entrano(testo):
    from lex.harness.comprensione import comprendi

    assert not comprendi(testo).per_harness
