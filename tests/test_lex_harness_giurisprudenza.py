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


def test_indice_precalcolato_per_norma_senza_archivio(tmp_path, monkeypatch):
    import json

    import lex.harness.giurisprudenza as G

    f = tmp_path / "g.json"
    f.write_text(json.dumps({"generato_il": "21/11/2026", "archivi": ["Cassazione (SentenzeWeb)"], "norme": {"cpc:617": [
        {"archivio": "Cassazione (SentenzeWeb)", "organo": "Corte di Cassazione — civile", "sezione": "3", "numero": "01234",
         "anno": "2023", "data": "2023-05-02", "url": "https://x", "massima": ""}], "cc:1137": []}}), encoding="utf-8")
    monkeypatch.setattr(G, "_PRECALCOLATE", f)
    e = G.per_norme(["cpc:617"])
    assert e is not None and e.pronunce[0].numero == "01234"
    assert G.per_norme(["cc:1137"]).pronunce == []        # nessuna pronuncia trovata: non si interroga l'archivio
    assert G.per_norme(["cc:9999"]) is None
