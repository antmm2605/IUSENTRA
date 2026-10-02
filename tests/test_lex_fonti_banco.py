"""Banco fonti di Lex (tests/lex_fonti_banco): la nuova ricerca FTS non deve scendere sotto la soglia."""

from __future__ import annotations

import pytest

from tests.lex_fonti_banco.valutazione import carica_corpus, carica_domande, esegui_banco

SOGLIA_RECALL_5 = 0.90
SOGLIA_RECALL_10 = 0.95
SOGLIA_MRR = 0.80


@pytest.fixture(scope="module")
def esito(tmp_path_factory):
    return esegui_banco(tmp_path_factory.mktemp("banco_fonti"))


def test_corpus_e_domande_ben_formati():
    corpus = carica_corpus()
    domande = carica_domande()
    assert len(domande) >= 40
    assert {d["materia"] for d in domande} >= {"civile", "processuale", "lavoro"}
    articoli = {(d["codice"], a["numero"]): a for d in corpus["documenti"] if d["vigenza"] == "VIGENTE" for a in d["articoli"]}
    for d in domande:
        for atteso in d["attesi"]:
            assert (atteso["codice"], atteso["articolo"]) in articoli, d["domanda"]
            assert not articoli[(atteso["codice"], atteso["articolo"])]["distrattore"]
    assert sum(1 for a in articoli.values() if a["distrattore"]) >= 5
    assert any(d["vigenza"] == "ORIGINALE" for d in corpus["documenti"])


def test_nuova_ricerca_sopra_soglia(esito):
    m = esito["ricerche"]["fts"]["metriche"]
    assert m["recall@5"] >= SOGLIA_RECALL_5, m
    assert m["recall@10"] >= SOGLIA_RECALL_10, m
    assert m["mrr"] >= SOGLIA_MRR, m


def test_nuova_ricerca_migliore_di_quella_attuale(esito):
    attuale = esito["ricerche"]["attuale"]["metriche"]
    nuova = esito["ricerche"]["fts"]["metriche"]
    assert nuova["recall@5"] > attuale["recall@5"]
    assert nuova["mrr"] > attuale["mrr"]


def test_versione_originale_non_duplica_la_vigente(esito):
    for classifica, vigenze in zip(esito["ricerche"]["fts"]["classifiche"], esito["ricerche"]["fts"]["vigenze"]):
        assert len(classifica) == len(vigenze), "una sola versione per articolo"
        assert "ORIGINALE" not in vigenze
