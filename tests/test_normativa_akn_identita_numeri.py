"""Regressioni dei casi documentati negli XML primari del censimento."""
import hashlib
from pathlib import Path
import sqlite3
import zipfile
import pytest
from lex.normativa.normattiva_akn_importer import parse_akn

XML = b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
<meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:2020-01-01;1"/>
<FRBRdate date="2020-01-01"/></FRBRWork><FRBRExpression><FRBRdate date="2020-01-02"/>
</FRBRExpression></identification></meta><body><article><num>Art. 1.</num>
<paragraph><content><p>Disciplina del corpo principale.</p></content></paragraph></article></body>
<attachments><attachment><doc name="Accordo-art. LABEL"><mainBody>
<p>Disciplina autonoma dell accordo.</p></mainBody></doc></attachment></attachments>
</act></akomaNtoso>'''


def parse(payload, entry="2020-01-01_20G00001_ORIGINALE_V0.xml"):
    return parse_akn(payload, zip_path=Path("primario.zip"), entry=entry,
                     collection_name="Fonte ufficiale", analizza_pertinenza=False)


@pytest.mark.parametrize("label,number", [("I-bis","I-bis"),("IV-bis","IV-bis"),
    ("1.","1"),("314/2","314/2"),("82/2","82/2"),("III a)","III a)"),("A","A"),("8 (aggiunta)","8 (aggiunta)"),
    ("12 (transitorio)","12 (transitorio)"),("24 (transitorio)","24 (transitorio)"),
    ("addizionale","addizionale"),("transitorio","transitorio"),("41 a)","41 a)"),
    ("46 a)","46 a)"),("31(I)","31(I)"),("3-bis (transitorio)","3-bis (transitorio)")])
def test_numero_primario_distinto_e_partizione_preservata(label, number):
    doc=parse(XML.replace(b"LABEL",label.encode()))
    assert len(doc.articles)==2
    assert doc.articles[1].article_number=="Art. "+number+"."
    assert doc.articles[1].partizione=="Accordo"
    assert "autonoma" not in doc.articles[0].article_text
    assert doc.articles[1].localizzatore_xml!=doc.articles[0].localizzatore_xml


@pytest.mark.parametrize("label", ["314//2","III xyz)","IIII-bis","../../1","31(IIII)","41 xyz)","12 (inventato)"])
def test_etichette_non_riscontrabili_non_diventano_numeri(label):
    with pytest.raises(ValueError,match="Numero dell.articolo"):
        parse(XML.replace(b"LABEL",label.encode()))


def costituzione():
    return XML.replace(b"urn:nir:stato:legge:2020-01-01;1",b"urn:nir:stato:costituzione").replace(
        b'<FRBRdate date="2020-01-01"/>',
        b'<FRBRdate date="0000-00-00"/><FRBRalias name="eli" value="eli/id/1947/12/27/047U0001/ORIGINAL"/>').replace(
        b'<FRBRdate date="2020-01-02"/>',b'<FRBRdate date="1948-01-01"/>').replace(
        b"Disciplina del corpo principale.",b"Data a Roma, addi' 27 dicembre 1947").replace(b"LABEL",b"I")


def test_data_costituzione_solo_dalla_firma_e_con_prova_preservata():
    payload=costituzione()
    doc=parse(payload,"1947-12-27_047U0001_ORIGINALE_V0.xml")
    assert doc.urn=="urn:nir:stato:costituzione:1947-12-27"
    assert doc.urn_originale_akn=="urn:nir:stato:costituzione"
    assert doc.data_atto=="1947-12-27"
    assert doc.data_atto_riscontro
    assert doc.xml_sha256==hashlib.sha256(payload).hexdigest()


def test_non_sostituire_la_firma_assente_con_data_pubblicazione():
    payload=costituzione().replace(b"Data a Roma, addi' 27 dicembre 1947",b"Testo privo di firma datata.")
    with pytest.raises(ValueError):
        parse(payload,"1947-12-27_047U0001_ORIGINALE_V0.xml")


def test_identita_eli_discordante_non_riparata_con_firma():
    payload=costituzione().replace(b"047U0001/ORIGINAL",b"047U9999/ORIGINAL")
    with pytest.raises(ValueError):
        parse(payload,"1947-12-27_047U0001_ORIGINALE_V0.xml")


def test_recupero_selettivo_legge_zip_intero_non_riscrive_originale(tmp_path):
    from lex.normativa.versioni_akn import importa_multiversione
    archive=tmp_path/"primario.zip"
    payload=XML.replace(b"LABEL",b"I")
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("2020-01-01_20G00001_ORIGINALE_V0.xml",payload)
        z.writestr("2020-01-01_20G00002_ORIGINALE_V0.xml",payload.replace(b"2020-01-01;1",b"2020-01-01;2"))
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    with sqlite3.connect(":memory:") as conn:
        result=importa_multiversione(conn,archivio=archive,sha256_atteso=digest,
            acquisita_utc="2020-01-03T10:00:00+00:00",identita_selezionate={("2020-01-01","20G00002")})
        assert result["errori"]==[] and result["atti_importati"]==1
        assert conn.execute("SELECT numero FROM normative_akn_chains").fetchall()==[("2",)]
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest


@pytest.mark.parametrize("preface", [
    b'<preface><docNumber>2</docNumber><docDate date="2020-01-01"/></preface>',
    b'<preface><docNumber>1</docNumber><docDate date="2020-01-03"/></preface>',
])
def test_intestazione_non_attribuisce_corpo_a_numero_o_data_diversi(preface):
    payload=XML.replace(b"</meta>",b"</meta>"+preface).replace(b"LABEL",b"I")
    with pytest.raises(ValueError,match="intestazione documentale discordante"):
        parse(payload)


def test_due_directory_stesso_codice_gu_non_fondono_due_atti(tmp_path):
    from lex.normativa.versioni_akn import importa_multiversione
    archive=tmp_path/"confezione-con-errore-primario.zip"
    valid=XML.replace(b"LABEL",b"I").replace(b"</meta>",b"</meta><preface><docNumber>1</docNumber></preface>")
    wrong=valid.replace(b"2020-01-01;1",b"2020-01-01;2")
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("LEGGE_20200101_1/2020-01-01_20G00001_ORIGINALE_V0.xml",valid)
        z.writestr("LEGGE_20200101_2/2020-01-01_20G00001_ORIGINALE_V0.xml",wrong)
    with sqlite3.connect(":memory:") as conn:
        result=importa_multiversione(conn,archivio=archive,
            sha256_atteso=hashlib.sha256(archive.read_bytes()).hexdigest(),
            acquisita_utc="2020-01-03T10:00:00+00:00")
        assert result["atti_importati"]==1
        assert len(result["errori"])==1
        assert "intestazione documentale discordante" in result["errori"][0]["errore"]
        assert conn.execute("SELECT numero FROM normative_akn_chains WHERE completa=1").fetchall()==[("1",)]


@pytest.mark.parametrize("numero",["1 (Raccolta 2020)","I (Raccolta 2020)"])
def test_anno_raccolta_coerente_non_cambia_numero_o_testo(numero):
    preface=("<preface><docNumber>"+numero+"</docNumber></preface>").encode()
    payload=XML.replace(b"</meta>",b"</meta>"+preface).replace(b"LABEL",b"I")
    doc=parse(payload)
    assert doc.urn=="urn:nir:stato:legge:2020-01-01;1"
    assert numero in doc.text_content


def test_anno_raccolta_discordante_non_normalizzato():
    payload=XML.replace(b"</meta>",b"</meta><preface><docNumber>1 (Raccolta 1999)</docNumber></preface>").replace(b"LABEL",b"I")
    with pytest.raises(ValueError,match="intestazione documentale discordante"):
        parse(payload)
