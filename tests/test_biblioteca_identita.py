import sqlite3

from lex.normativa.biblioteca.identita import risolvi_articolo


def catalogo():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE normative_documents(id INTEGER,collection_name TEXT,urn TEXT,redazione_id TEXT,titolo TEXT,numero TEXT,data_atto TEXT)")
    c.execute("CREATE TABLE normative_articles(id INTEGER,document_id INTEGER,article_number TEXT,article_text TEXT)")
    c.executemany("INSERT INTO normative_documents VALUES(?,?,?,?,?,?,?)",[(1,"Lex fonti: allegato1","urn:uno","2026","Allegato uno","79","2011-05-23"),(2,"Lex fonti: corpo","urn:uno","2026","Corpo decreto","79","2011-05-23"),(3,"Lex fonti: legge_300_1970","urn:statuto","2026","Statuto","300","1970-05-20")])
    c.executemany("INSERT INTO normative_articles VALUES(?,?,?,?)",[(1,1,"2","Testo allegato."),(2,2,"2","Testo corpo."),(3,1,"43","Testo articolo 43."),(4,3,"18","Testo statuto.")])
    return c


def test_partition_requires_real_metadata_not_first_match():
    c=catalogo()
    assert len(risolvi_articolo(c,{"chiave":"79/2011","articolo":"2"}))==2
    exact=risolvi_articolo(c,{"chiave":"79/2011","articolo":"2","titolo_atto":"Allegato uno","inizio_testo":"Testo allegato."})
    assert len(exact)==1 and exact[0][0]["id"]==1
    assert risolvi_articolo(c,{"chiave":"79/2011","articolo":"43"})[0][0]["id"]==1


def test_known_code_uses_actual_catalog_identity():
    c=catalogo()
    assert risolvi_articolo(c,{"chiave":"statuto_lavoratori","articolo":"18"})[0][0]["id"]==3
    assert risolvi_articolo(c,{"chiave":"('c', 'legge_300_1970')","articolo":"18"})[0][0]["id"]==3


def test_number_year_does_not_guess_type_or_edition():
    c=catalogo()
    c.execute("INSERT INTO normative_documents VALUES(4,'Lex fonti: altro','urn:diverso','2026','Altro','79','2011-01-01')")
    assert not risolvi_articolo(c,{"chiave":"79/2011","articolo":"43"})
    c.execute("INSERT INTO normative_documents VALUES(5,'Lex fonti: allegato1','urn:uno','2025','Allegato uno','79','2011-05-23')")
    assert not risolvi_articolo(c,{"chiave":"allegato1","articolo":"43"})
    assert risolvi_articolo(c,{"chiave":"allegato1","articolo":"43","edizione":"2026"})


def test_filtro_catalogo_usa_numeri_romani_storici_e_nodi_nativi(tmp_path):
    import json
    import pytest
    from lex.normativa.consultazione import importa_fonti,articoli
    source=tmp_path/'pacchetto'/'atti';source.mkdir(parents=True)
    numbers=['Art. XIX.','Art. I-bis.','Art. 314/2.','Art. 473-bis.14.','Art. I.','Art. 1.']
    rows=[dict(chiave='legge_prova',urn='urn:nir:stato:legge:2020-01-01;1',titolo_atto='Numerazioni di prova',atto='legge',articolo=number,testo=number+' Testo integrale controllato relativo alla sola disposizione indicata.') for number in numbers]
    (source/'articoli.jsonl').write_text('\n'.join(json.dumps(x) for x in rows))
    db=tmp_path/'codici_leggi.sqlite';importa_fonti(source.parent,db,'2026-10-26')
    from lex.normativa.biblioteca.identita import indicizza_numeri_articolo,espressione_numero_articolo_sql
    with sqlite3.connect(db) as conn:
        name=indicizza_numeri_articolo(conn)
        plan=conn.execute('EXPLAIN QUERY PLAN SELECT a.id FROM normative_articles a WHERE '+espressione_numero_articolo_sql('a.article_number')+' = ?',('xix',)).fetchall()
        assert any(name in row[3] for row in plan)
    for query,expected in zip(['XIX','I bis','314/2','473-bis.14','I','1'],numbers):
        result=articoli(db,article=query)
        assert result['total']==1
        assert result['items'][0]['number']==expected
    for bad in ['1,2','1/2/3','IIII','1..']:
        with pytest.raises(ValueError):articoli(db,article=bad)
