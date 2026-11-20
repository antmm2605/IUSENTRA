"""Fase 5: pronunce dagli archivi in sola lettura, con estremi e tempo massimo."""
from __future__ import annotations

import time


class _Corpus:
    def __init__(self, righe, attesa=0.0):
        self.righe, self.attesa = righe, attesa

    def cerca_sentenze(self, **kw):
        time.sleep(self.attesa)
        return self.righe


RIGA = {"organo_giudicante": "Corte di Cassazione", "sezione": "VI-2", "numero_sentenza": "21568", "anno_sentenza": "2017",
        "data_deposito": "2017-09-18", "url_pagina_ufficiale": "https://www.italgiure.giustizia.it/x",
        "massima_ufficiale": "La sospensione feriale non si applica alle opposizioni esecutive."}


def test_estremi_da_tutti_gli_archivi():
    from lex.harness.giurisprudenza import per_estremi, sezione

    e = per_estremi("21568", "2017", sorgenti=lambda: [("Cassazione (SentenzeWeb)", _Corpus([RIGA])),
                                                       ("archivio dello studio", _Corpus([]))])
    assert [p.estremi for p in e.pronunce] == ["Corte di Cassazione, sez. VI-2, n. 21568/2017 (dep. 2017-09-18)"]
    assert "21568/2017" in sezione(e) and "massima" not in sezione(e)


def test_archivio_lento_non_blocca_la_risposta():
    from lex.harness.giurisprudenza import cerca

    t = time.time()
    e = cerca("art. 617 c.p.c.", secondi=0.5, sorgenti=lambda: [("Cassazione (SentenzeWeb)", _Corpus([RIGA], attesa=3))])
    assert time.time() - t < 2 and e.stato == "archivio non disponibile" and "nessuna risposta" in e.errori[0]


def test_nessun_archivio_dichiarato():
    from lex.harness.giurisprudenza import cerca

    assert cerca("x", sorgenti=lambda: []).stato.startswith("nessun archivio")
