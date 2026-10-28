"""Regressioni da eseguire dopo la conclusione delle acquisizioni."""
from datetime import date
from types import SimpleNamespace

from lex.normativa.biblioteca.ricerca_fonti import integra_fonti
from lex.procedura_atti.provenienza import sha256_testo

URN = "urn:nir:stato:regio.decreto:1942-03-16;262"


def _riga(testo, ident, **extra):
    return {"titolo": "Codice civile", "url_origine": URN, "articolo_o_chunk": "1",
            "normative_full_text": testo, "normative_full_text_sha256": sha256_testo(testo),
            "archive_catalog": "biblioteca_codici_leggi", "document_id": 10,
            "normative_article_id": ident, "data_acquisizione": "2026-10-26",
            "vigenza": "EDIZIONE_ACQUISITA", "metadata": {"redazione_id": "2026-10-26", "consultazione_fonte": {"raccolto_il": "2026-10-26"}}, **extra}


def _integra(monkeypatch, tmp_path, righe, base=None):
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_normattiva",
                        lambda *a, **k: righe)
    fonti = SimpleNamespace(fonti={1: base} if base else {}, fonti_ref=([
        {"n": 1, "atto": URN, "articolo": "1", "provenienza": {"url": "", "sha256": sha256_testo(base)}}
    ] if base else []), pendenze=[])
    answers = iter(['{"istituti":[],"riferimenti":[]}', '{"scelti":[1,2]}'])
    result = integra_fonti(fonti, richiesta="testo della domanda", fatti="fatti del caso",
                          biblioteca=tmp_path / "codici.sqlite", oggi=date(2026,10,26),
                          data_riferimento=date(2026,10,26),
                          chiama_modello=lambda *a: (next(answers), "modello-simulato"))
    return fonti, result


def test_stesso_numero_testo_diverso_non_elimina_partizione(monkeypatch, tmp_path):
    base = "La persona acquista la capacita giuridica dalla nascita e conserva i diritti previsti dalla legge."
    altro = "Le fonti del diritto sono le leggi, i regolamenti e gli usi secondo le disposizioni preliminari."
    fonti, result = _integra(monkeypatch, tmp_path, [_riga(altro, 202)], base)
    assert list(fonti.fonti.values()) == [base, altro]
    assert result["riscontri_gia_nella_scheda"][0]["testo_coincidente"] is False
    assert fonti.fonti_ref[-1]["provenienza"]["article_id"] == 202


def test_partizioni_distinte_stesso_testo_non_fuse(monkeypatch, tmp_path):
    text = "La disposizione si applica ai soggetti indicati nel presente articolo secondo le condizioni previste."
    fonti, result = _integra(monkeypatch, tmp_path, [_riga(text,101), _riga(text,202)])
    assert result["candidati_chiusi"] == 2
    assert [f["provenienza"]["article_id"] for f in fonti.fonti_ref] == [101,202]


def test_chunk_dello_stesso_articolo_una_sola_fonte(monkeypatch, tmp_path):
    text = "La disposizione si applica ai soggetti indicati nel presente articolo secondo le condizioni previste."
    fonti, result = _integra(monkeypatch, tmp_path, [_riga(text,101,chunk_rowid=1), _riga(text,101,chunk_rowid=2)])
    assert result["candidati_chiusi"] == 1
    assert len(fonti.fonti) == 1


def test_provenienza_acquisita_non_sostituita_con_articolo_di_altro_allegato(monkeypatch, tmp_path):
    text="Il decreto approva il testo allegato, mantenendo distinta la disposizione di approvazione."
    url="https://www.gazzettaufficiale.it/eli/id/1942/04/04/042U0262/sg"
    row=_riga(text,101,metadata={"redazione_id":"2026-10-26","consultazione_fonte":{"raccolto_il":"2026-10-26","url":url}})
    fonti,_=_integra(monkeypatch,tmp_path,[row])
    assert fonti.fonti_ref[0]["provenienza"]["url"]==url
    row=_riga(text,101)
    fonti,_=_integra(monkeypatch,tmp_path,[row])
    assert "~art" not in fonti.fonti_ref[0]["provenienza"]["url"]
    assert fonti.fonti_ref[0]["provenienza"]["article_id"]==101
