from copy import deepcopy

from lex.normativa.provenienza_edizione import edizione_archiviata,etichetta_edizione
from lex.procedura_atti.impronte import impronta_fonti


def test_versione_concreta_non_e_etichetta_vigente():
    source=edizione_archiviata({"redazione_id":"2026-10-26","document_sha256":"a"*64,
        "consultazione_provenienza":'{"espressione_dal":"2026-01-01","zip_sha256":"'+"b"*64+'"}'})
    assert source["espressione_dal"]=="2026-01-01"
    assert source["zip_sha256"]=="b"*64
    assert "2026-10-26" in etichetta_edizione(source)
    assert "a"*64 in etichetta_edizione(source)
    assert "applicabilita_al_fascicolo_verificata" not in source


def test_stesso_testo_e_stessa_url_ma_ricevuta_diversa_cambiano_impronta():
    case={"fonti":{1:"Testo identico della norma"},"fonti_ref":[{"n":1,"atto":"norma","articolo":"1",
          "provenienza":{"url":"https://www.normattiva.it/","edizione_archiviata":{"xml_sha256":"a"*64}}}]}
    other=deepcopy(case)
    other["fonti_ref"][0]["provenienza"]["edizione_archiviata"]["xml_sha256"]="b"*64
    assert case["fonti"]==other["fonti"]
    assert impronta_fonti(case)!=impronta_fonti(other)


def test_provenienza_esclude_percorsi_locali_e_non_inventa_date():
    result=edizione_archiviata({"consultazione_provenienza":{"zip_path":"/private/local/file",
        "localizzatore_xml":"/akomaNtoso/act/body/article[1]"},"vigenza":"VIGENTE"})
    assert "zip_path" not in result
    assert result["localizzatore_xml"].endswith("article[1]")
    assert "versione_formale_dal" not in result
    assert etichetta_edizione(result)=="edizione da riscontrare"


def test_cambia_il_riscontro_della_data_ma_non_il_testo_rifiuta_vecchia_impronta():
    first={"urn_originale_akn":"urn:nir:stato:costituzione", "data_atto_riscontro":{
        "origine":"firma_nel_testo_ufficiale", "data":"1947-12-27",
        "estratto":"Data a Roma, addi' 27 dicembre 1947", "sha256_testo_riscontro":"a"*64}}
    second=deepcopy(first)
    second["data_atto_riscontro"]["sha256_testo_riscontro"]="b"*64
    case={"fonti":{1:"Testo immutato della disposizione"},"fonti_ref":[{"n":1,"atto":"Costituzione",
        "articolo":"1","provenienza":{"edizione_archiviata":edizione_archiviata({"consultazione_provenienza":first})}}]}
    other=deepcopy(case)
    other["fonti_ref"][0]["provenienza"]["edizione_archiviata"]=edizione_archiviata({"consultazione_provenienza":second})
    assert case["fonti"]==other["fonti"]
    assert case["fonti_ref"][0]["provenienza"]["edizione_archiviata"]["urn_originale_akn"]==first["urn_originale_akn"]
    assert impronta_fonti(case)!=impronta_fonti(other)


def test_acquisizione_non_si_inventa_dalla_importazione_e_rispetta_fuso():
    from lex.normativa.provenienza_edizione import data_acquisizione_documentata
    assert data_acquisizione_documentata({'imported_at':'2026-10-26T09:00:00+00:00'})==''
    assert data_acquisizione_documentata({'acquisita_utc':'2026-10-25T23:30:00+00:00'})=='26/10/2026'
    assert data_acquisizione_documentata({'acquisita_utc':'2026-10-25T23:30:00'})==''
    assert data_acquisizione_documentata({'raccolto_il':'2026-10-25'})=='25/10/2026'
    assert data_acquisizione_documentata({'raccolto_il':'2026-02-30'})==''


def test_derivato_tecnico_con_intervallo_non_proietta_la_ricezione_nel_futuro():
    from datetime import date
    from lex.normativa.provenienza_edizione import riscontro_alla_data,edizione_archiviata
    sha="a"*64
    technical={"sha256_payload_ufficiale":sha,"originale_non_modificato":True,
        "derivato_non_esportazione_ufficiale":True,"normalizzatore_sha256":"b"*64,
        "corpo_normativo_c14n_immutato_sha256":"c"*64,"testo_visibile_immutato_sha256":"d"*64}
    prov={"sha256_payload_ufficiale":sha,"metadati_tecnici_riscontrati":technical,
        "intervallo_formale_riscontrato":True,"versione_formale_dal":"2023-10-22",
        "versione_formale_al_escluso":None,"acquisita_utc":"2026-10-26T10:00:00+00:00"}
    edition=edizione_archiviata({"consultazione_provenienza":prov})
    assert riscontro_alla_data(edition,date(2025,1,1)) is True
    assert riscontro_alla_data(edition,date(2026,10,27)) is None
    edition["metadati_tecnici_riscontrati"]=dict(technical,sha256_payload_ufficiale="0"*64)
    assert riscontro_alla_data(edition,date(2025,1,1)) is None
