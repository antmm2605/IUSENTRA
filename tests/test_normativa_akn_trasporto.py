"""Regressioni dei formati effettivamente incontrati negli export ufficiali."""
import base64
import hashlib
from pathlib import Path

import pytest

from lex.normativa.normattiva_akn_importer import decodifica_xml_akn, parse_akn


XML = b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
<meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:2020-01-01;1"/>
<FRBRdate date="2020-01-01"/></FRBRWork><FRBRExpression><FRBRdate date="2020-01-02"/>
</FRBRExpression></identification></meta><body><article><num>Art. 1.</num>
<paragraph><content><p>Corpo principale integrale.</p></content></paragraph></article></body>
<attachments><attachment><doc name="Allegato 1-art. 71 bis"><mainBody>
<p>Corpo autonomo dell'articolo dell'allegato.</p></mainBody></doc></attachment></attachments>
</act></akomaNtoso>'''


def leggi(payload):
    return parse_akn(payload,zip_path=Path("ufficiale.zip"),
                     entry="LEGGE_20200101_1/2020-01-01_20G00001_ORIGINALE_V0.xml",
                     collection_name="Fonte ufficiale",analizza_pertinenza=False)


def test_base64_una_sola_decodifica_con_due_impronte():
    plain=leggi(XML)
    encoded=base64.b64encode(XML)
    wrapped=leggi(encoded)
    assert wrapped.text_content==plain.text_content
    assert wrapped.xml_sha256==hashlib.sha256(encoded).hexdigest()
    assert wrapped.xml_decodificato_sha256==plain.xml_sha256
    assert wrapped.codifica_trasporto=="base64"
    assert plain.codifica_trasporto=="xml"


def test_allegato_con_spazio_bis_resta_partizione_distinta():
    doc=leggi(XML)
    assert len(doc.articles)==2
    assert doc.articles[1].article_number=="Art. 71 bis."
    assert doc.articles[1].partizione=="Allegato 1"
    assert "autonomo" not in doc.articles[0].article_text


@pytest.mark.parametrize("payload",[b"risposta non XML",base64.b64encode(b"errore"),
                                    base64.b64encode(base64.b64encode(XML))])
def test_non_interpretare_errori_o_codifiche_multiple_come_testi(payload):
    with pytest.raises(ValueError):
        decodifica_xml_akn(payload)


def test_numerazione_romana_del_trattato_conservata_senza_conversione():
    doc=leggi(XML.replace(b"Allegato 1-art. 71 bis",b"Accordo-art. XIX"))
    assert doc.articles[1].article_number=="Art. XIX."
    assert doc.articles[1].partizione=="Accordo"


def test_numerazione_romana_non_canonica_non_promossa():
    with pytest.raises(ValueError,match="Numero dell.articolo"):
        leggi(XML.replace(b"Allegato 1-art. 71 bis",b"Accordo-art. IIII"))


def test_fotogramma_iniziale_stessa_decorrenza_conservato_senza_due_versioni_leggibili(tmp_path):
    import sqlite3
    import zipfile
    from lex.normativa.versioni_akn import importa_multiversione,leggi_versione

    archive=tmp_path/"ufficiale.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("LEGGE_20200101_1/2020-01-01_20G00001_ORIGINALE_V0.xml",XML)
        z.writestr("LEGGE_20200101_1/2020-01-01_20G00001_VIGENZA_2020-01-02_V1.xml",base64.b64encode(XML))
    with sqlite3.connect(":memory:") as conn:
        result=importa_multiversione(conn,archivio=archive,
            sha256_atteso=hashlib.sha256(archive.read_bytes()).hexdigest(),
            acquisita_utc="2020-01-03T10:00:00+00:00")
        assert result["errori"]==[]
        assert result["versioni_importate"]==2
        assert conn.execute("SELECT dal,al_escluso FROM normative_akn_editions WHERE ordinal=0").fetchone()==("2020-01-02","2020-01-02")
        rows=leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-02")
        assert len(rows)==2
        assert all(row["codifica_trasporto"]=="base64" for row in rows)
        assert all(row["xml_decodificato_sha256"]==hashlib.sha256(XML).hexdigest() for row in rows)
        assert all(row["xml_entry"].endswith("V1.xml") for row in rows)
        assert leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-01")==[]
        assert leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-04")==[]


def test_articolo_di_accordo_con_suffisso_letterale_non_separato():
    doc=leggi(XML.replace(b"Allegato 1-art. 71 bis",b"Accordo-art. 7a"))
    assert doc.articles[1].article_number=="Art. 7a."
    assert doc.articles[1].partizione=="Accordo"


def test_cache_con_revisione_precedente_non_evade_rilettura(tmp_path,monkeypatch):
    import sqlite3
    import zipfile
    from lex.normativa import versioni_akn as cache

    archive=tmp_path/"ufficiale.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("LEGGE_20200101_1/2020-01-01_20G00001_ORIGINALE_V0.xml",XML)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    with sqlite3.connect(":memory:") as conn:
        for revision in ("a"*64,"b"*64):
            monkeypatch.setattr(cache,"impronta_lettore",lambda value=revision:value)
            result=cache.importa_multiversione(conn,archivio=archive,sha256_atteso=digest,acquisita_utc="2020-01-03T10:00:00+00:00")
            assert result["errori"]==[]
            assert result["atti_importati"]==1
        assert conn.execute("SELECT COUNT(*) FROM normative_akn_chains").fetchone()[0]==2
        assert {r[0] for r in conn.execute("SELECT lettore_sha256 FROM normative_akn_chains")}=={"a"*64,"b"*64}
        rows=cache.leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-02")
        assert rows and all(r["lettore_sha256"]=="b"*64 for r in rows)
        monkeypatch.setattr(cache,"impronta_lettore",lambda:"c"*64)
        assert cache.leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-02")==[]
        assert conn.execute("SELECT COUNT(*) FROM normative_akn_chains").fetchone()[0]==2


def test_metadati_tecnici_non_diventano_corpo():
    payload=XML.replace(b"<meta>",b"<meta><notes><note><p>SOLO METADATI TECNICI</p></note></notes>")
    assert "SOLO METADATI TECNICI" not in leggi(payload).text_content


def test_originale_con_articolo_solo_rubrica_non_e_integrale():
    payload=XML.replace(b"<paragraph><content><p>Corpo principale integrale.</p></content></paragraph>",b"")
    assert leggi(payload).qualita_corpo!="testo_acquisito"

def test_zip_di_sole_cartelle_non_diventa_catena_completa(tmp_path):
    import sqlite3
    import zipfile
    from lex.normativa.versioni_akn import importa_multiversione

    archive=tmp_path/"risposta-ufficiale-senza-testo.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("DECRETO_DEL_PRESIDENTE_DELLA_REPUBBLICA_20260804_183/",b"")
    with sqlite3.connect(":memory:") as conn:
        result=importa_multiversione(conn,archivio=archive,
            sha256_atteso=hashlib.sha256(archive.read_bytes()).hexdigest(),acquisita_utc="2026-10-26T05:00:00+00:00")
        assert result["atti_importati"]==0
        assert any("senza documenti XML" in e["errore"] for e in result["errori"])
        assert conn.execute("SELECT COUNT(*) FROM normative_akn_chains").fetchone()[0]==0