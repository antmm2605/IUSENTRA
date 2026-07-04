from __future__ import annotations

import pct.giurisprudenza_corpus as corpus_module
from lex.autonomy.discovery import LocalCorpusSearchProvider, _archive_http_url

_SENTENZA_CITABILE = {
    "id": 1,
    "organo_giudicante": "Corte di Cassazione",
    "sezione": "III civile",
    "numero_sentenza": "12345",
    "anno_sentenza": 2026,
    "titolo": "Cass. civ. n. 12345/2026 — responsabilità aquiliana",
    "massima_ufficiale": "In tema di responsabilità ex art. 2043 c.c., il danno ingiusto richiede la prova del nesso causale.",
    "principio_sintetico": "Onere della prova del nesso causale a carico del danneggiato.",
    "stato_verifica": "verificata",
    "url_pagina_ufficiale": "https://www.cortedicassazione.it/it/civile_dettaglio.page?id=12345",
    "url_pdf_ufficiale": "",
    "ecli": "ECLI:IT:CASS:2026:12345CIV",
}
_SENTENZA_NON_VERIFICATA = {**_SENTENZA_CITABILE, "id": 2, "stato_verifica": "da_verificare",
                            "url_pagina_ufficiale": "https://www.cortedicassazione.it/it/civile_dettaglio.page?id=2"}
_SENTENZA_SENZA_MASSIMA = {**_SENTENZA_CITABILE, "id": 3, "massima_ufficiale": "", "principio_sintetico": "",
                           "url_pagina_ufficiale": "https://www.cortedicassazione.it/it/civile_dettaglio.page?id=3"}


def _provider_con_corpus(tmp_path, monkeypatch, rows):
    db = tmp_path / "giurisprudenza_corpus.db"
    corpus_module.GestioneCorpusGiurisprudenza(str(db))  # crea lo schema reale su tmp
    monkeypatch.setattr(corpus_module.GestioneCorpusGiurisprudenza, "cerca_sentenze", lambda self, **kw: list(rows))
    return LocalCorpusSearchProvider(db_path=db)


def test_sentenza_citabile_diventa_candidato_con_massima(tmp_path, monkeypatch):
    provider = _provider_con_corpus(tmp_path, monkeypatch, [_SENTENZA_CITABILE])
    candidates = provider.search("responsabilità aquiliana site:cortedicassazione.it", limit=3)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.url.startswith("https://www.cortedicassazione.it/")
    assert "nesso causale" in candidate.content
    assert candidate.discovered_by == "corpus_locale"
    assert candidate.source_id == "corpus_locale:giurisprudenza"


def test_sentenza_non_verificata_scartata_fail_closed(tmp_path, monkeypatch):
    provider = _provider_con_corpus(tmp_path, monkeypatch, [_SENTENZA_NON_VERIFICATA])
    assert provider.search("responsabilità", limit=3) == []


def test_sentenza_senza_massima_scartata(tmp_path, monkeypatch):
    provider = _provider_con_corpus(tmp_path, monkeypatch, [_SENTENZA_SENZA_MASSIMA])
    assert provider.search("responsabilità", limit=3) == []


def test_corpus_assente_vuoto_senza_creare_il_db(tmp_path):
    db = tmp_path / "assente" / "giurisprudenza_corpus.db"
    provider = LocalCorpusSearchProvider(db_path=db)
    assert provider.search("responsabilità aquiliana", limit=3) == []
    assert not db.exists()  # sola lettura: mai creare il corpus da qui
    assert not db.parent.exists()


def test_dedup_per_url_e_tetto(tmp_path, monkeypatch):
    provider = _provider_con_corpus(tmp_path, monkeypatch, [_SENTENZA_CITABILE, dict(_SENTENZA_CITABILE)])
    assert len(provider.search("responsabilità", limit=5)) == 1


def test_urn_vuoto_non_produce_ancora_generica():
    # Regressione run #4: una riga con "urn:" nudo generava l'ancora
    # https://www.normattiva.it/uri-res/N2Ls?urn: (non onesta).
    assert _archive_http_url("urn:") == ""
    assert _archive_http_url("urn:nir:stato:legge:1990-08-07;241").endswith("legge:1990-08-07;241")
