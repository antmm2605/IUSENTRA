"""Giurisprudenza: FTS5 in OR con stopword/radici e ordinamento bm25."""

from pathlib import Path

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza, _fts_or_query


def _sentenza(numero: int, titolo: str, principio: str, *, stato: str = "non_verificata", pdf: bool = False) -> dict:
    return {
        "fonte": {"codice": "cassazione", "nome": "Corte di Cassazione", "tipo_fonte": "ufficiale", "ente": "Corte di Cassazione", "url_home": "https://www.cortedicassazione.it/"},
        "numero_sentenza": str(numero),
        "anno_sentenza": 2024,
        "organo_giudicante": "Corte di Cassazione",
        "titolo": titolo,
        "principio_sintetico": principio,
        "testo_integrale": principio,
        "stato_verifica": stato,
        "pdf_ufficiale_presente": pdf,
    }


def test_query_or_senza_stopword_e_con_radici():
    q = _fts_or_query("Quali sono i presupposti della responsabilità extracontrattuale?")
    assert " OR " in q and '"respons"*' in q and '"extracontrattual"*' in q
    assert "quali" not in q and '"sono"' not in q and '"della"' not in q


def test_ricerca_in_or_trova_corrispondenze_parziali_e_ordina_per_bm25(tmp_path: Path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "g_corpus.db"))
    # Verificata e con PDF (criteri storici favorevoli) ma poco pertinente.
    corpus.salva_sentenza(_sentenza(1, "Locazione commerciale", "Il conduttore risponde dei canoni scaduti; responsabilita limitata.", stato="verificata", pdf=True))
    # Non verificata ma molto pertinente: contiene entrambi i termini.
    corpus.salva_sentenza(_sentenza(2, "Responsabilita extracontrattuale", "La responsabilita extracontrattuale richiede danno ingiusto, nesso causale e colpa."))
    corpus.salva_sentenza(_sentenza(3, "Appalto", "Termini di decadenza nell'appalto."))
    righe = corpus.cerca_sentenze(q="Quali sono i presupposti della responsabilita' extracontrattuale?")
    numeri = [r["numero_sentenza"] for r in righe]
    assert numeri[0] == "2", numeri
    assert "1" in numeri and "3" not in numeri  # OR: corrispondenza parziale ammessa
    assert righe[0]["punteggio_bm25"] <= righe[1]["punteggio_bm25"]


def test_senza_testo_resta_l_ordinamento_storico(tmp_path: Path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "g_corpus.db"))
    corpus.salva_sentenza(_sentenza(1, "A", "x", stato="verificata", pdf=True))
    corpus.salva_sentenza(_sentenza(2, "B", "y"))
    assert [r["numero_sentenza"] for r in corpus.cerca_sentenze()][0] == "1"
