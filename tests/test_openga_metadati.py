from lex.retrieval import giurisprudenza as retrieval
from pct.giurisprudenza import GestioneGiurisprudenza
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from pct.giurisprudenza_evidenze import (
    riferimento_metadati_confermato,
    solo_metadati,
)
from pct.giurisprudenza_evidenze import (
    testo_metadati as descrivi_metadati,
)


def record():
    return {
        "fonte_codice": "openga",
        "source_system": "openga",
        "organo_giudicante": "TAR Lazio",
        "numero_sentenza": "123",
        "anno_sentenza": 2025,
        "url_pagina_ufficiale": "https://openga.giustizia-amministrativa.it/dataset/risorsa",
        "fonte_ufficiale_confermata": True,
        "stato_verifica": "parzialmente_verificata",
        "oggetto": "Diniego del permesso di soggiorno",
        "esito": "IMPROCEDIBILE",
        "massima_ufficiale": "Una massima NON dimostrata",
        "principio_sintetico": "Un principio NON dimostrato",
        "abstract": "Una motivazione NON dimostrata",
        "testo_integrale_presente": False,
    }


def test_solo_metadati_non_diventa_contenuto_neanche_con_flag_verificato():
    row = record()
    row["verified_reference"] = True
    assert solo_metadati(row) and riferimento_metadati_confermato(row)
    assert retrieval._riferimento_verificato(row, row["url_pagina_ufficiale"]) is False
    text = descrivi_metadati(row)
    assert row["oggetto"] in text and row["esito"] in text
    assert "NON dimostrata" not in text and "NON dimostrato" not in text
    row["url_pagina_ufficiale"] = "https://openga.giustizia-amministrativa.it.evil.test/"
    assert not riferimento_metadati_confermato(row)


def test_retrieval_non_espone_vecchie_pseudomassime(monkeypatch):
    row = {**record(), "id": 1, "titolo": "TAR Lazio 123/2025"}

    class Gestore:
        def cerca_corpus_professionale(self, **kwargs):
            return [row]

    monkeypatch.setattr(retrieval, "_gestore_giurisprudenza", lambda: Gestore())
    assert retrieval.search_giurisprudenza_sources("permesso di soggiorno") == []
    source = retrieval.search_giurisprudenza_sources("permesso di soggiorno", include_metadata_only=True)[0]
    assert source.metadata["evidence_scope"] == "metadata_only"
    assert source.metadata["verified_metadata"] is True
    assert source.metadata["verified_reference"] is False
    assert source.metadata["principio"] == source.metadata["massima_ufficiale"] == ""
    assert "NON dimostrata" not in source.excerpt
    assert "Esito riportato nel dataset: IMPROCEDIBILE" in source.excerpt


def test_mapper_non_promuove_oggetto_e_non_altera_le_altre_fonti(tmp_path):
    gestore = GestioneGiurisprudenza(str(tmp_path / "giurisprudenza.json"))
    row = {
        **record(),
        "numero_provvedimento": "123",
        "anno": 2025,
        "abstract": "Oggetto originale del ricorso",
        "massima": "Vecchio oggetto scambiato per massima",
        "principio_diritto": "Annotazione non dimostrata",
        "source_system": "openga",
    }
    mapped = gestore._corpus_payload_from_record(row)
    assert mapped["anno_sentenza"] == 2025
    assert mapped["oggetto"] == "Oggetto originale del ricorso"
    assert mapped["massima_ufficiale"] == mapped["principio_sintetico"] == ""
    assert mapped["massime"] == mapped["principi_diritto"] == []
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "separato.db"))
    assert not corpus.can_cite_sentenza(row)
    row["fonte_codice"] = row["source_system"] = "cassazione"
    row["url_pagina_ufficiale"] = "https://www.cortedicassazione.it/provvedimento"
    assert not solo_metadati(row)
    assert corpus.can_cite_sentenza(row)


def test_corpus_esclude_metadati_prima_del_ranking_solo_contenuto(tmp_path):
    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "corpus.db"))
    for code in ["openga", "cassazione"]:
        corpus.salva_sentenza(
            {
                "fonte": {"codice": code, "nome": code, "tipo_fonte": "ufficiale"},
                "numero_sentenza": "123",
                "anno_sentenza": 2025,
                "organo_giudicante": code,
                "titolo": "Permesso di soggiorno",
                "massima_ufficiale": "Permesso di soggiorno e termini",
                "stato_verifica": "parzialmente_verificata",
                "url_pagina_ufficiale": "https://"
                + ("openga.giustizia-amministrativa.it" if code == "openga" else "www.cortedicassazione.it")
                + "/record",
            }
        )
    all_rows = corpus.cerca_sentenze(q="permesso")
    assert {row["fonte_codice"] for row in all_rows} == {"openga", "cassazione"}
    legal_rows = corpus.cerca_sentenze(q="permesso", solo_contenuto=True)
    assert [row["fonte_codice"] for row in legal_rows] == ["cassazione"]


def test_openga_con_testo_acquisito_non_e_confuso_con_solo_metadati():
    row = record()
    row["testo_integrale_presente"] = True
    assert not solo_metadati(row)
