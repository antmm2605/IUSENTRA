"""Prova sul campo: il cancello di ancoraggio su trenta pagine anonimizzate (rassegna Reducto).

Obiettivi dichiarati: nessun valore inventato che passa, meno del 2% di valori
veri bloccati a torto. Il lettore simulato riscrive i valori veri nelle forme
tipiche di un modello («18 luglio 2026», «1375», «EUR 259.00», «n. 812/2026»)
e aggiunge valori plausibili ma assenti dalla pagina.
"""

from __future__ import annotations

import pytest

from pct.collaudo_ai.pagine_anonime import PAGINE
from pct.collaudo_ai.valuta_pagine import (
    canonico,
    riepilogo,
    valuta_con_modello,
    valuta_pagina,
    valuta_simulato,
)
from pct.provenienza_ai import VERSIONE_CANCELLO, cancello_ancoraggio


def test_trenta_pagine_con_valori_veri_nel_testo():
    assert len(PAGINE) == 30 and len({p.id for p in PAGINE}) == 30
    for pagina in PAGINE:
        assert pagina.valori, pagina.id
        for valore in pagina.valori:
            assert canonico(valore.tipo, valore.valore), (pagina.id, valore)


def test_obiettivi_del_cancello_sul_lettore_simulato():
    sintesi = riepilogo(valuta_simulato())
    assert sintesi["inventate"] >= 60
    assert sintesi["inventate_passate"] == 0
    assert sintesi["quota_blocchi_a_torto"] < 0.02, sintesi
    # I valori guastati dal riconoscimento ottico sono errori di lettura, non del cancello.
    assert sintesi["lettura_valori_nel_testo"] < sintesi["valori_veri"]


@pytest.mark.parametrize("valore, testo", [
    ("18 luglio 2026", "Trani, 18/07/2026"),
    ("2026-07-18", "Trani, 18 luglio 2026"),
    ("1375", "SALDO FINALE € 1.375,00"),
    ("EUR 259.00", "Importo pagato: 259,00 EUR"),
    ("214.6", "spese documentate 214,60"),
    ("145,50 euro", "ed € 145,50 per esborsi"),
    ("n. 812/2026", "ricorso numero di registro generale 812 del 2026"),
    ("301234567890123456", "Codice avviso: 3012 3456 7890 1234 56"),
    ("R.G. n. 1234/2025", "RG n. 1234/2025"),
])
def test_stesso_valore_in_altra_forma_passa(valore, testo):
    assert cancello_ancoraggio({"v": valore}, testo).ammesso, cancello_ancoraggio({"v": valore}, testo).to_dict()


@pytest.mark.parametrize("valore, testo", [
    ("19/07/2026", "Trani, 18/07/2026"),
    ("€ 1.234,00", "R.G. n. 1234/2026"),
    ("1.375,50", "SALDO FINALE € 1.375,00"),
    ("342", "R.G. 1234/2026 del 2026"),
    ("n. 813/2026", "ricorso numero di registro generale 812 del 2026"),
])
def test_valori_inventati_si_bloccano(valore, testo):
    assert not cancello_ancoraggio({"v": valore}, testo).ammesso


def test_versione_del_cancello_dichiarata():
    assert VERSIONE_CANCELLO.endswith(".v2")


def test_valutazione_con_modello_finto_per_stadi():
    pagina = next(p for p in PAGINE if p.id == "p07")  # F24 con errori di lettura

    def genera(domanda, schema):
        assert "valori" in schema["properties"]
        return '{"valori": [{"tipo": "importo", "valore": "1.250,00", "descrizione": "tributo"}, {"tipo": "importo", "valore": "1.375,00", "descrizione": "saldo"}, {"tipo": "data", "valore": "17/06/2026", "descrizione": "inventata"}]}'

    esito = valuta_con_modello(pagina, genera, modello="finto")
    per_valore = {p.valore: p for p in esito.proposte}
    assert per_valore["1.375,00"].vero and per_valore["1.375,00"].ammesso
    # «l.250,00» nel testo: il valore giusto non è stato letto, il blocco è della lettura.
    assert per_valore["1.250,00"].vero and not per_valore["1.250,00"].nel_testo and not per_valore["1.250,00"].ammesso
    assert not per_valore["17/06/2026"].vero and not per_valore["17/06/2026"].ammesso
    sintesi = riepilogo([esito])
    assert sintesi["vere_bloccate_a_torto"] == 0 and sintesi["vere_bloccate_per_lettura"] == 1


def test_proposte_senza_tipo_si_classificano():
    pagina = PAGINE[0]
    esito = valuta_pagina(pagina, [{"valore": "23/09/2026"}, {"valore": "€ 3.200,00"}, {"valore": "345/2026"}], lettore="t")
    assert [p.tipo for p in esito.proposte] == ["data", "importo", "numero"]
    assert all(p.vero and p.ammesso for p in esito.proposte)


def test_segnaposto_e_parole_spezzate_non_si_ancorano():
    # «n.d.» dice che il valore non c'è: non si controlla e non diventa un valore.
    assert cancello_ancoraggio({"importo": "n.d."}, "Il giorno in data 20/09/2026").controlli == ()
    # Il testo si confronta a parole intere: «n d» non è dentro «in data».
    assert not cancello_ancoraggio({"nome": "n d x"}, "Il giorno in data x").ammesso
    assert cancello_ancoraggio({"nome": "Edilnova S.r.l."}, "alla Edilnova S.r.l. all'indirizzo").ammesso


def test_valori_scritti_ma_non_elencati_non_sono_inventati():
    pagina = next(p for p in PAGINE if p.id == "p20")
    esito = valuta_pagina(pagina, [{"tipo": "data", "valore": "31/12/2024"}, {"tipo": "importo", "valore": "2,50%"}, {"tipo": "data", "valore": "02/01/2025"}], lettore="t")
    assert [(p.vero, p.presente) for p in esito.proposte] == [(False, True), (False, True), (False, False)]
    assert riepilogo([esito])["inventate"] == 1
