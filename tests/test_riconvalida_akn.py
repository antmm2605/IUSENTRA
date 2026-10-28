"""La compatibilità del programma non certifica catene non rilette."""
import hashlib
import sqlite3
import zipfile
from contextlib import closing
import pytest
from lex.normativa.riconvalida_akn import ArchivioRiscontrato, riconvalida_catena
from lex.normativa.versioni_akn import importa_multiversione, impronta_lettore

XML=b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act>
<meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:2020-01-01;1"/>
<FRBRdate date="2020-01-01"/></FRBRWork><FRBRExpression><FRBRdate date="2020-01-02"/>
</FRBRExpression></identification></meta><body><article><num>Art. 1.</num>
<paragraph><content><p>Corpo normativo da conservare integralmente.</p></content></paragraph>
</article></body></act></akomaNtoso>'''


def prepara(tmp_path):
    archive=tmp_path/"primario.zip"
    with zipfile.ZipFile(archive,"w") as z:
        z.writestr("2020-01-01_20G00001_ORIGINALE_V0.xml",XML)
        z.writestr("2020-01-01_20G00001_VIGENZA_2020-01-03_V1.xml",XML)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    conn=sqlite3.connect(":memory:")
    result=importa_multiversione(conn,archivio=archive,sha256_atteso=digest,
        acquisita_utc="2020-01-04T10:00:00+00:00")
    assert result["errori"]==[]
    chain=conn.execute("SELECT id FROM normative_akn_chains").fetchone()[0]
    return archive,digest,conn,chain


def test_solo_dopo_tutti_fotogrammi_riletti_si_qualifica_la_catena(tmp_path):
    archive,digest,conn,chain=prepara(tmp_path)
    with closing(conn), closing(ArchivioRiscontrato(archive,digest)) as source:
        report=riconvalida_catena(conn,chain_id=chain,archivio=source,cartella_prove=tmp_path/"prove")
        row=conn.execute("SELECT riscontro_lettore_sha256,riscontro_contenuti_sha256 FROM normative_akn_chains").fetchone()
        assert row==(impronta_lettore(),report["sha256"])
        assert report["versioni"]==2 and report["articoli"]==2


def test_articolo_alterato_ultimo_fotogramma_non_lascia_qualificazione_parziale(tmp_path):
    archive,digest,conn,chain=prepara(tmp_path)
    with closing(conn), closing(ArchivioRiscontrato(archive,digest)) as source:
        conn.execute("UPDATE normative_akn_articles SET sha256_testo=? WHERE edition_id=(SELECT MAX(id) FROM normative_akn_editions)",("0"*64,))
        conn.commit()
        with pytest.raises(ValueError,match="articolo discordanti"):
            riconvalida_catena(conn,chain_id=chain,archivio=source,cartella_prove=tmp_path/"prove")
        assert conn.execute("SELECT riscontro_lettore_sha256 FROM normative_akn_chains").fetchone()==("",)
        assert not (tmp_path/"prove").exists()


def test_manifesto_globale_non_qualifica_una_catena_non_riletta(tmp_path,monkeypatch):
    from lex.normativa import versioni_akn as cache
    from lex.normativa import lettori_attestati as policy
    archive,digest,conn,chain=prepara(tmp_path)
    with closing(conn):
        origin=conn.execute("SELECT lettore_sha256 FROM normative_akn_chains").fetchone()[0]
        runtime="b"*64
        monkeypatch.setattr(cache,"impronta_lettore",lambda:runtime)
        monkeypatch.setattr(policy,"politica_lettori",lambda _:policy.PoliticaLettori(frozenset((origin,runtime))))
        rows=cache.leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-03")
        assert rows==[]
        conn.execute("UPDATE normative_akn_chains SET riscontro_lettore_sha256=?,riscontro_contenuti_sha256=?",(runtime,"non-una-prova"))
        assert cache.leggi_versione(conn,urn="urn:nir:stato:legge:2020-01-01;1",data_riferimento="2020-01-03")==[]


def test_confronto_worker_sola_lettura_non_attesta_sql(tmp_path):
    archive,digest,conn,chain=prepara(tmp_path)
    conn.commit();conn.execute("PRAGMA query_only=ON")
    with closing(conn), closing(ArchivioRiscontrato(archive,digest)) as source:
        report=riconvalida_catena(conn,chain_id=chain,archivio=source,
            cartella_prove=tmp_path/"prove-ro",commit=False,attesta_sql=False)
        assert report["versioni"]==2 and report["articoli"]==2
        assert conn.execute("SELECT riscontro_lettore_sha256,riscontro_contenuti_sha256 FROM normative_akn_chains").fetchone()==("", "")
        from pathlib import Path
        assert hashlib.sha256(Path(report["file"]).read_bytes()).hexdigest()==report["sha256"]


def test_primario_cambiato_dopo_sha_coordinatore_rifiutato(tmp_path):
    from tools.riconvalida_cache_akn_parallela import ArchivioDelegato
    archive,digest,conn,chain=prepara(tmp_path);conn.close()
    with closing(ArchivioRiscontrato(archive,digest)) as source:
        st=source.stat;token={"path":str(source.path),"sha256":digest,"stat":[st.st_size,st.st_mtime_ns,st.st_ino]}
    with archive.open("ab") as stream:stream.write(b"alterato")
    with pytest.raises(RuntimeError,match="Primario cambiato"):
        ArchivioDelegato(token)
