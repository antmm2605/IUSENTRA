"""La provenienza UE resta EUR-Lex e non è ricostruita come un URN Normattiva."""
import json

from lex.normativa.consultazione import url_fonte_da_metadata,url_ufficiale_valido


def test_urlex_ufficiale_acquisito_come_json_o_oggetto_conservato():
    url="https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32021R0782"
    for source in [{"url":url},json.dumps({"url":url})]:
        assert url_fonte_da_metadata({"consultazione_fonte":source})==url


def test_metadati_non_interpretabili_non_inventano_un_collegamento():
    for source in ["{",[],None,{"url":"http://eur-lex.europa.eu/"}]:
        assert url_fonte_da_metadata({"consultazione_fonte":source})==""


def test_nome_del_dominio_e_credenziali_nel_collegamento_verificati():
    assert url_ufficiale_valido("https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1994-01-21;53")
    assert not url_ufficiale_valido("https://eur-lex.europa.eu.esempio.invalid/testo")
    assert not url_ufficiale_valido("https://utente:password@www.normattiva.it/testo")


def test_risultato_ue_nella_chat_mantiene_la_provenienza_urlex():
    from lex.retrieval.normativa import _archive_row_to_source

    url="https://eur-lex.europa.eu/legal-content/IT/TXT/?uri=CELEX:32021R0782"
    row={"titolo":"Regolamento UE 2021/782","url_origine":"urn:nir:unione.europea:regolamento:2021-04-29;782",
         "testo":"Articolo 1. Testo della fonte pubblica.","articolo_o_chunk":"1",
         "metadata":{"consultazione_fonte":json.dumps({"url":url})}}
    result=_archive_row_to_source(row,source_type="normativa_normattiva",default_title="Normattiva")
    assert result.metadata["official_url"]==url
    assert result.metadata["urn"]==row["url_origine"]


def test_identificatore_interno_ue_senza_provenienza_non_diventa_link_ufficiale():
    from lex.retrieval.normativa import _archive_row_to_source

    row={"titolo":"Regolamento UE 2021/782","url_origine":"urn:nir:unione.europea:regolamento:2021-04-29;782",
         "testo":"Articolo 1. Testo della fonte pubblica.","articolo_o_chunk":"1"}
    result=_archive_row_to_source(row,source_type="normativa_normattiva",default_title="Normattiva")
    assert result.metadata["official_url"]==""
    assert result.metadata["verified_reference"] is False
    assert result.metadata["source_provenance_pending"] is True


def test_identita_del_testo_ue_confrontata_con_il_celex_richiesto():
    import pytest
    from lex.normativa.ue_regolamenti import AttoUE,RegolamentoUE,verifica_identita

    received=AttoUE(titolo="Regolamento UE 2021/782",data_atto="2021-04-29",tipo="UE",numero="782",anno="2021",formato="html")
    verifica_identita(received,RegolamentoUE("32021R0782","trasporto ferroviario"))
    with pytest.raises(ValueError,match="Identità"):
        verifica_identita(received,RegolamentoUE("32022R2065","servizi digitali"))
