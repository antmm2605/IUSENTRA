"""Pertinenza di «Cerca norme e sentenze» sugli estremi (collaudo 21/11/2026)."""
from web.services import react_legal_intelligence_bridge as bridge
from web.services.ricerca_legale_sentenza_citata import estremi_sentenza, filtra


def test_cass_su_riconosce_gli_estremi_della_sentenza():
    assert estremi_sentenza("Cass. S.U. 5425/2021") == {"organo": "cassazione", "numero": "5425", "anno": "2021", "sezione": "U"}
    assert estremi_sentenza("legge 178/2020") is None
    assert estremi_sentenza("art. 2021 c.c.") is None


def test_cass_su_non_propone_legge_di_bilancio_ne_art_2021():
    records = [
        {"title": "Legge 30 dicembre 2020, n. 178 — Bilancio di previsione 2021", "sourceLabel": "Normattiva", "registryNumber": "1"},
        {"title": "Codice civile — Art. 2021", "sourceLabel": "Normattiva", "registryNumber": "2021"},
        {"title": "Cassazione civile, Sezioni Unite, sentenza", "sourceLabel": "Corte di Cassazione — SentenzeWeb",
         "registryNumber": "05425/2021", "courtSection": "U"},
        {"title": "Cassazione sez. 3", "sourceLabel": "Corte di Cassazione — SentenzeWeb", "registryNumber": "05425/2021", "courtSection": "3"},
    ]
    trovati, estremi = filtra(records, "Cass. S.U. 5425/2021")
    assert estremi["sezione"] == "U"
    assert [r["courtSection"] for r in trovati] == ["U"]


def test_art_155_cpc_e_l_articolo_del_codice_non_delle_disposizioni_di_attuazione():
    records = [
        {"registryNumber": "155", "title": "Disposizioni per l'attuazione del codice di procedura civile — Art. 155", "sourceLabel": "Normattiva"},
        {"registryNumber": "155", "title": "Codice di procedura civile — Art. 155", "sourceLabel": "Normattiva"},
    ]
    assert [r["title"] for r in bridge._filter_records_for_exact_reference(records, "art. 155 c.p.c.")] == [
        "Codice di procedura civile — Art. 155"]


def test_data_della_norma_e_quella_del_testo_acquisito_non_dell_atto():
    scheda = bridge._safe_official_archive_record(
        {"document_id": 4, "titolo": "Codice civile — Art. 2043", "data": "1942-03-16",
         "data_acquisizione": "2026-11-11 12:03:57", "url_origine": "https://www.normattiva.it/x"}, 1, archive="normattiva")
    assert scheda["date"] == "2026-11-11"
