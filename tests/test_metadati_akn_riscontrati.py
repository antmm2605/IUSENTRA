"""Derivati tecnici ammessi solo con riscontro nel corpo, senza riscrivere la fonte."""
import hashlib
import pytest
from lex.normativa.metadati_akn_riscontrati import normalizza_metadati, leggi_documento
from tests.test_normativa_akn_trasporto import XML


def test_suffisso_errato_nei_metadati_riscontrato_nel_corpo():
    raw=XML.replace(b"Allegato 1-art. 71 bis",b"Protocollo-art. V-qinquies").replace(
        b"Corpo autonomo dell'articolo dell'allegato.",b"Articolo V quinquies Corpo autonomo dell'articolo dell'allegato.")
    doc,proof=leggi_documento(raw)
    assert doc.articles[1].article_number=="Art. V-quinquies."
    assert "Articolo V quinquies Corpo autonomo" in doc.articles[1].article_text
    assert proof["sha256_payload_ufficiale"]==hashlib.sha256(raw).hexdigest()
    assert proof["originale_non_modificato"] is True
    assert proof["derivato_non_esportazione_ufficiale"] is True
    assert b"V-qinquies" in raw


@pytest.mark.parametrize("label",[b"V-quater",b"IV-qinquies",b"V-sbagliato"])
def test_non_sostituire_un_altro_articolo_o_correggere_senza_riscontro(label):
    raw=XML.replace(b"Allegato 1-art. 71 bis",b"Protocollo-art. "+label).replace(
        b"Corpo autonomo dell'articolo dell'allegato.",b"Articolo V quinquies Corpo autonomo dell'articolo dell'allegato.")
    normalized,proof=normalizza_metadati(raw)
    assert normalized==raw and proof is None


def test_risposta_ordinaria_non_riscritta():
    normalized,proof=normalizza_metadati(XML)
    assert normalized is XML and proof is None


def _source(raw=XML):
    if b"<publication" not in raw:
        raw=raw.replace(b"<meta>",b'<meta><publication date="2020-01-01"/>').replace(b"<FRBRWork>",b'<FRBRWork><FRBRalias value="eli/id/2020/01/01/20G00001/CONSOLIDATED/20200102"/>')
    from lex.normativa.biblioteca.normattiva_akn import AttoScaricato
    return AttoScaricato("urn:nir:stato:legge:2020-01-01;1",raw,"Fixture","20200101","20G00001","20201026",
        "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2020-01-01;1",hashlib.sha256(raw).hexdigest())


def test_conversione_conserva_allegato_e_data_letterale_distinte_dalla_richiesta():
    from lex.normativa.biblioteca.normattiva_akn import converti
    rows=converti(_source(),"legge_1_2020","2020-10-26")
    assert len(rows)==2
    assert rows[0]["chiave"]=="legge_1_2020"
    assert rows[1]["chiave"].startswith("legge_1_2020_parte_")
    assert rows[1]["provenienza_integrazione"]["partizione_xml"]=="Allegato 1"
    assert all(r["consolidato_al"]=="2020-01-02" for r in rows)
    assert all(r["provenienza_integrazione"]["vigenza_richiesta"]=="2020-10-26" for r in rows)


def test_un_articolo_abrogato_non_elimina_gli_altri_articoli_dell_atto():
    from lex.normativa.biblioteca.normattiva_akn import converti
    raw=XML.replace(b"Corpo principale integrale.",b"ARTICOLO ABROGATO")
    rows=converti(_source(raw),"legge_1_2020","2020-10-26")
    assert len(rows)==2 and rows[0]["senza_testo"] is True
    assert rows[1]["senza_testo"] is False


def test_rilettura_fisica_impedisce_corpo_o_provenienza_inventati(tmp_path):
    from copy import deepcopy
    from lex.normativa.biblioteca.normattiva_akn import converti
    from lex.normativa.metadati_akn_riscontrati import verifica_riga_puntuale
    (tmp_path/"prove").mkdir();source=_source();path=tmp_path/"prove"/(source.sha256_xml+".xml");path.write_bytes(source.xml)
    row=converti(source,"legge_1_2020","2020-10-26")[0]
    row["provenienza_integrazione"]["file_xml_originale"]="prove/"+path.name
    cache={};assert verifica_riga_puntuale(tmp_path,row,cache=cache)
    altered=deepcopy(row);altered["testo"]+=" Inventato."
    with pytest.raises(ValueError,match="testo"):verifica_riga_puntuale(tmp_path,altered,cache=cache)
    path.write_bytes(XML+b" ")
    with pytest.raises(ValueError,match="cambiata"):verifica_riga_puntuale(tmp_path,row,cache=cache)


def test_impronta_raw_discordante_non_diventa_fonte():
    from lex.normativa.biblioteca.normattiva_akn import converti
    source=_source();source.sha256_xml="0"*64
    with pytest.raises(ValueError,match="Impronta"):converti(source,"legge_1_2020","2020-10-26")


def test_due_etichette_omonime_restano_distinte_per_localizzatore_xml():
    from lex.normativa.biblioteca.normattiva_akn import converti
    raw=XML.replace(b"</attachments>",b'<attachment><doc name="Allegato 1-art. 71 bis"><mainBody><p>Secondo articolo omonimo distinto nella fonte.</p></mainBody></doc></attachment></attachments>')
    rows=converti(_source(raw),"legge_1_2020","2020-10-26")
    annex=[r for r in rows if r["articolo"]=="71bis"]
    assert len(annex)==2
    assert len({r["chiave"] for r in annex})==2
    assert len({r["provenienza_integrazione"]["localizzatore_xml"] for r in annex})==2


def test_chiave_di_partizione_rileggibile_dal_lettore_esatto(tmp_path):
    import json
    from lex.normativa.biblioteca.normattiva_akn import converti
    from lex.normativa.biblioteca.lettura import leggi_articoli
    from lex.normativa.consultazione import importa_fonti
    source=_source();rows=converti(source,"legge_1_2020","2020-10-26")
    (tmp_path/"atti").mkdir();(tmp_path/"prove").mkdir()
    (tmp_path/"prove"/(source.sha256_xml+".xml")).write_bytes(source.xml)
    for row in rows:
        row["provenienza_integrazione"]["file_xml_originale"]="prove/"+source.sha256_xml+".xml"
        (tmp_path/"atti"/(row["chiave"]+".jsonl")).write_text(json.dumps(row),encoding="utf-8")
    db=tmp_path/"book.sqlite";importa_fonti(tmp_path,db,"2020-10-26")
    annex=rows[1];result=leggi_articoli(db,[{"chiave":annex["chiave"],"articolo":annex["articolo"],"edizione":"2020-01-02"}])
    assert result["lettura_completa"] is True
    assert result["articoli"][0]["testo"]==annex["testo"]


def test_provenienza_costituzione_serializzata_conserva_identita_pubblicazione(tmp_path):
    import json
    from lex.normativa.biblioteca.normattiva_akn import AttoScaricato,converti
    from lex.normativa.metadati_akn_riscontrati import verifica_riga_puntuale
    from tests.test_normativa_akn_identita_numeri import costituzione
    raw=costituzione().replace(b"</meta>",b'<publication date="1947-12-27"/></meta><preface><docDate date="0000-00-00"/></preface>')
    source=AttoScaricato("urn:nir:stato:costituzione:1947-12-27",raw,"Fixture","19471227","047U0001","19480101",
        "https://www.normattiva.it/atto/caricaDettaglioAtto?atto.dataPubblicazioneGazzetta=1947-12-27&atto.codiceRedazionale=047U0001",hashlib.sha256(raw).hexdigest())
    row=converti(source,"costituzione","2026-10-26")[0]
    (tmp_path/"prove").mkdir();(tmp_path/"prove"/(source.sha256_xml+".xml")).write_bytes(raw)
    row["provenienza_integrazione"]["file_xml_originale"]="prove/"+source.sha256_xml+".xml"
    restored=json.loads(json.dumps(row))
    assert restored["provenienza_integrazione"]["identita_pubblicazione"]==["1947-12-27","047U0001"]
    assert verifica_riga_puntuale(tmp_path,restored)
    restored["provenienza_integrazione"]["identita_pubblicazione"][1]="047U9999"
    with pytest.raises(ValueError,match="Provenienza"):verifica_riga_puntuale(tmp_path,restored)


def test_url_articolo_diversi_non_rileggono_ogni_volta_intero_xml(tmp_path,monkeypatch):
    from copy import deepcopy
    from lex.normativa.biblioteca import normattiva_akn
    from lex.normativa.metadati_akn_riscontrati import verifica_riga_puntuale
    from lex.testi_ufficiali import collegamento_normattiva
    source=_source();rows=normattiva_akn.converti(source,"legge_1_2020","2020-10-26")
    (tmp_path/"prove").mkdir();path=tmp_path/"prove"/(source.sha256_xml+".xml");path.write_bytes(source.xml)
    calls=[];original=normattiva_akn.converti
    def counted(*args,**kwargs):
        calls.append(1)
        return original(*args,**kwargs)
    monkeypatch.setattr(normattiva_akn,"converti",counted)
    cache={}
    for row in rows:
        row["url"]=collegamento_normattiva(row["urn"],row["articolo"])
        row["provenienza_integrazione"]["file_xml_originale"]="prove/"+path.name
        assert verifica_riga_puntuale(tmp_path,row,cache=cache)
    assert len(calls)==1
    altered=deepcopy(rows[-1]);altered["testo"]+=" Testo estraneo aggiunto."
    with pytest.raises(ValueError,match="testo"):
        verifica_riga_puntuale(tmp_path,altered,cache=cache)
    assert len(calls)==1
