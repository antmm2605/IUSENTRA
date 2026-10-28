import hashlib
import json
import sqlite3
from lxml import etree
from lex.normativa.applicabilita import Applicabilita
from lex.normativa.struttura import percorso_xml, salva_proiezione, espandi
from lex.normativa.biblioteca.normattiva_akn import AttoScaricato, converti
from lex.normativa.consultazione import importa_fonti

XML = b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
<meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:1994-01-21;53"/>
<FRBRalias name="eli" value="eli/id/1994/01/31/094G0053/CONSOLIDATED/20261025"/>
<FRBRdate date="1994-01-21"/></FRBRWork><FRBRExpression><FRBRdate date="2026-10-25"/></FRBRExpression></identification><publication date="1994-01-31"/></meta>
<preface><docTitle>Fixture non giuridica</docTitle></preface><body><book eId="book1"><num>Libro I</num><heading>Libro</heading>
<chapter eId="chapter1"><num>Capo I</num><heading>Capo uno</heading>
<article><num>Art. 1</num><paragraph>Testo uno.</paragraph></article>
<article><num>Art. 2</num><paragraph>Testo due.</paragraph></article></chapter>
<chapter eId="chapter2"><num>Capo II</num><heading>Capo due</heading>
<article><num>Art. 3</num><paragraph>Testo tre.</paragraph></article></chapter></book></body></act></akomaNtoso>'''
URN = "urn:nir:stato:legge:1994-01-21;53"
URL = "https://www.normattiva.it/uri-res/N2Ls?" + URN

def test_structure_import_and_expansion_no_cross_chapter_or_edition(tmp_path):
    act = AttoScaricato(URN, XML, "fixture", "19940131", "094G0053", "20261025", URL, hashlib.sha256(XML).hexdigest())
    rows = converti(act, "legge_53_1994", "2026-10-25")
    assert [n["tipo"] for n in rows[0]["struttura_normativa"]] == ["libro", "capo"]
    package = tmp_path / "package" / "atti"; package.mkdir(parents=True)
    (package / "fixture.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    db = tmp_path / "codici_leggi.sqlite";importa_fonti(package.parent, db, "2026-10-25")
    with sqlite3.connect(db) as conn:
        ids = dict(conn.execute("SELECT article_number,id FROM normative_articles"))
        r = espandi(conn, [ids["2"]], per_partizione=3, massimo=4, verifica_applicabilita=lambda _: Applicabilita("applicabile", ("fixture",)))
        assert r["diretti"] == [ids["2"]]
        assert [x["article_id"] for x in r["aggiunti"]] == [ids["1"]]
        assert ids["3"] not in [x["article_id"] for x in r["aggiunti"]]
        assert espandi(conn, [ids["2"]], massimo=0)["aggiunti"] == []

def test_node_identity_bound_to_xml_version_and_act():
    tree = etree.fromstring(XML);a=tree.xpath("//*[local-name()='article']")[0];sha=hashlib.sha256(XML).hexdigest()
    first=percorso_xml(a, URN, "2026-10-25", sha)
    assert first[-1]["id"] != percorso_xml(a, URN, "2027-01-01", sha)[-1]["id"]
    assert first[-1]["id"] != percorso_xml(a, URN, "2026-10-25", "a"*64)[-1]["id"]

def test_missing_structure_preserves_direct_results():
    with sqlite3.connect(":memory:") as c:
        assert espandi(c,[8,8,12]) == {"diretti":[8,12],"aggiunti":[],"stato":"struttura_assente"}


def test_xml_order_bis_ter_and_temporal_gate(tmp_path):
    xml = XML.replace(b'Art. 1', b'Art. 473-bis.12').replace(b'Art. 2', b'Art. 473-bis.2').replace(b'Art. 3', b'Art. 473-bis.3')
    act = AttoScaricato(URN, xml, "fixture", "19940131", "094G0053", "20261025", URL, hashlib.sha256(xml).hexdigest())
    rows = converti(act, "legge_53_1994", "2026-10-25")
    package = tmp_path / "package" / "atti"; package.mkdir(parents=True)
    (package / "fixture.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    db = tmp_path / "test.sqlite"; importa_fonti(package.parent, db, "2026-10-25")
    with sqlite3.connect(db) as conn:
        ids = [x[0] for x in conn.execute("SELECT id FROM normative_articles ORDER BY id")]
        assert espandi(conn, [ids[1]])["aggiunti"] == []
        for status in ("da_verificare", "non_applicabile"):
            result = espandi(conn, [ids[1]], verifica_applicabilita=lambda _, s=status: Applicabilita(s, ("fixture",)))
            assert result["aggiunti"] == []
            assert result["esclusi_temporali"][0]["stato"] == status
        result = espandi(conn, [ids[1]], verifica_applicabilita=lambda _: Applicabilita("applicabile", ("fixture",)))
        assert [x["article_id"] for x in result["aggiunti"]] == [ids[0]]
        assert result["diretti"] == [ids[1]]
        conn.execute("UPDATE normative_structure SET node_json=?", (json.dumps({"tipo":"titolo"}),))
        assert espandi(conn, [ids[1]], verifica_applicabilita=lambda _: Applicabilita("applicabile", ("fixture",)))["aggiunti"] == []
