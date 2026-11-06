"""Giurisprudenza della scheda: verifica delle citazioni e decisioni per norma dall'archivio."""

from pct.giurisprudenza_alimentazione import leggi_citazioni
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from pct.guida_pratica.giurisprudenza_scheda import decisioni_per_norme, sigla_norma, verifica_citazioni


def _decisione(owner, numero, anno, sezione, testo):
    owner.salva_sentenza({"uuid_interno": f"sentenzeweb:snciv{anno}{sezione}{numero}O", "fonte_codice": "cassazione_sentenzeweb",
                          "fonte_nome": "Corte di Cassazione — SentenzeWeb", "tipo_fonte": "ufficiale", "organo_giudicante": "Corte di Cassazione — civile",
                          "sezione": sezione, "numero_sentenza": numero, "anno_sentenza": anno, "data_deposito": f"{anno}-05-10",
                          "titolo": f"Cassazione snciv {numero}/{anno}", "url_pagina_ufficiale": f"https://www.italgiure.giustizia.it/x?id={numero}",
                          "testo_integrale_presente": True, "testo_integrale": testo})


def _archivio(tmp_path):
    owner = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    _decisione(owner, "20053", 2024, "U", "Giurisdizione ex art. 63 del d.lgs. n. 165/2001 e art. 2087 c.c. (Cass., Sez. U, n. 24418 del 2010).")
    _decisione(owner, "33700", 2025, "L", "Violazione dell'art. 2087 c.c.")
    leggi_citazioni(owner)
    return tmp_path / "giurisprudenza_corpus.db"


def test_citazioni_vere_e_false(tmp_path):
    db = _archivio(tmp_path)
    esiti = verifica_citazioni([{"fonte": "Cass. SU 20053/2024"}, {"fonte": "Cass. SU 14897/2021"}, {"fonte": "Cass. SU 24418/2010 (anatocismo)"},
                                {"fonte": "Cass. SU 33700/2025"}], cassazione=db, costituzionale=None)
    assert [e["verificata"] for e in esiti] == [True, False, True, False]
    assert "richiamata da" in esiti[2]["come"]


def test_decisioni_per_norma_ordinate_per_pertinenza(tmp_path):
    db = _archivio(tmp_path)
    decisioni = decisioni_per_norme([("D.Lgs. 165/2001 (TUPI)", "63"), ("c.c.", "2087")], cassazione=db)
    assert [d["decisione"] for d in decisioni] == ["Cass. SU 20053/2024", "Cass. lav. 33700/2025"]
    assert decisioni[0]["perche"] == "applica 2 delle norme della scheda (Sezioni Unite)"


def test_senza_archivio_nessuna_decisione_e_nessuna_verifica(tmp_path):
    assert decisioni_per_norme([("c.c.", "2087")], cassazione=tmp_path / "manca.db") == []
    assert verifica_citazioni([{"fonte": "Cass. SU 20053/2024"}], cassazione=None, costituzionale=None)[0]["verificata"] is False


def test_sigla_delle_leggi():
    assert sigla_norma("D.Lgs. 165/2001 (TUPI)") == "D.Lgs. 165/2001" and sigla_norma("c.c.") == "c.c."
