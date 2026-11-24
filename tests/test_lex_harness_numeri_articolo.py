"""Un numero isolato (anno, RG, importo senza «euro») non è un articolo: i segnali lo vogliono con «art.» o col codice."""
from __future__ import annotations

import re

from lex.harness.fattispecie.materie import SCHEDE
from lex.harness.norme import piano


def _segnali(s):
    return [x for x in (*s.segnali, *s.alcuni, *s.esclusi)]


def test_nessun_segnale_con_numero_di_articolo_isolato():
    for s in SCHEDE:
        for x in _segnali(s):
            if s.regola.startswith(("pi_carta",)):
                continue
            assert not re.search(r"(?<=[|(])\d{3,4}(?=[|)])", x), (s.regola, x[:80])


def test_numeri_isolati_non_attivano_le_regole():
    for frase in ("Nella causa RG 650/2025 il giudice ha fissato l'udienza: cosa devo fare?",
                  "Ho speso 700 per la riparazione dell'auto e il meccanico non ha fatto il lavoro.",
                  "Nel 2050 scade il mutuo: posso rinegoziarlo?"):
        t = piano(frase)
        for s in SCHEDE:
            for x in s.segnali:
                if re.search(x, t) and re.search(r"650|700|2050", x):
                    m = re.search(x, t).group(0)
                    assert not re.fullmatch(r"\d+", m.strip()), (frase, s.regola, m)


def test_numeri_con_art_o_codice_riconosciuti():
    t = piano("Opposizione tardiva ex art. 650 c.p.c. e ricorso ex 700 c.p.c.")
    trovate = {s.regola for s in SCHEDE if all(re.search(x, t) for x in s.segnali)}
    assert trovate, "nessuna regola riconosce art. 650 / 700 c.p.c."
