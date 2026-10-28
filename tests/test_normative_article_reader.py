"""Il link legge la disposizione selezionata, senza confondere articoli, atti e versioni."""
import hashlib
import sqlite3

import pytest

from tests.test_api_schede_fonti import _biblioteca
from web.services.normative_article_reader import (
    ArticoloCambiato,
    destinazione_ufficiale,
    documento_html,
    numero_articolo,
    risolvi,
)


def test_lettura_puntuale_per_atto_articolo_e_impronta_senza_scritture(tmp_path):
    db = _biblioteca(tmp_path)
    prima = hashlib.sha256(db.read_bytes()).hexdigest()
    r = risolvi(db, atto="codice_procedura_civile", articolo="196")
    assert 'Testo vigente 196' in r['text'] and r['number']=='196'
    assert '~art196' in r['article_url'] and ';1443:1' in r['article_url']
    assert risolvi(db, atto="codice_procedura_civile", articolo="196", sha=r['sha256'])['id']==r['id']
    assert hashlib.sha256(db.read_bytes()).hexdigest()==prima
    with pytest.raises(ArticoloCambiato):
        risolvi(db, atto="codice_procedura_civile", articolo="196", sha='0'*64)
    with pytest.raises(LookupError):
        risolvi(db, atto="codice_procedura_civile", articolo="99999")


def test_id_non_puo_essere_sostituito_con_altro_articolo_o_altra_fonte(tmp_path):
    db = _biblioteca(tmp_path)
    a = risolvi(db, atto="codice_procedura_civile", articolo="196")
    assert risolvi(db, ident=a['id'], articolo='196')['text']==a['text']
    with pytest.raises(LookupError):
        risolvi(db, ident=a['id'], articolo='192')
    with pytest.raises(LookupError):
        risolvi(db, articolo='196', url='https://example.test/altro')
    for arg in ['../196', '<script>', '196;drop table', '196,192']:
        with pytest.raises(ValueError):numero_articolo(arg)


def test_piu_testi_distinti_non_vengono_uniti_o_scelti_per_somiglianza(tmp_path):
    db = _biblioteca(tmp_path)
    with sqlite3.connect(db) as c:
        # Una numerazione omonima è selezionabile soltanto per ID o impronta.
        row=c.execute('SELECT * FROM normative_articles LIMIT 1').fetchone()
        columns=[r[1] for r in c.execute('PRAGMA table_info(normative_articles)')]
        data=dict(zip(columns,row));data.pop('id');data['article_key']+='-alt';data['article_text']='Art. 196. Altro allegato, testo differente.';data['article_number']='196'
        c.execute('INSERT INTO normative_articles ('+','.join(data)+') VALUES ('+','.join('?' for _ in data)+')',list(data.values()))
    with pytest.raises(ArticoloCambiato):risolvi(db, atto='codice_procedura_civile',articolo='196')


def test_documento_html_mostra_testo_intero_e_sorgente_senza_embed_esterno(tmp_path):
    db = _biblioteca(tmp_path)
    r = risolvi(db, atto='codice_procedura_civile',articolo='196')
    r['text'] += '<script>alert(1)</script>'
    html = documento_html(r)
    assert '&lt;script&gt;' in html and '<script>' not in html
    assert '<iframe' not in html and r['sha256'] in html
    assert "target='_blank'" in html and 'noopener noreferrer' in html
    assert r['article_url'] in html


def test_codici_allegati_distinti_e_articoli_suffissati():
    cpc={'source_url':'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443','urn':'urn:nir:stato:regio.decreto:1940-10-28;1443','number':'167','text':'Art.167 Testo'}
    assert ';1443:1~art167' in destinazione_ufficiale(cpc)
    cc={**cpc,'urn':'urn:nir:stato:regio.decreto:1942-03-16;262','source_url':'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262','number':'2043'}
    assert ';262:2~art2043' in destinazione_ufficiale(cc)
    assert numero_articolo('Art. 171-ter')=='171ter'
    assert numero_articolo('473-bis.12')=='473bis.12'
    pdf={**cpc,'source_url':'https://www.consigliodistrettuale.it/fonte.pdf'}
    assert destinazione_ufficiale(pdf)==''  # Non inventare la pagina del PDF.


def test_api_autenticata_rende_articolo_e_rifiuta_impronta_vecchia(tmp_path):
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    db = _biblioteca(tmp_path)
    app = _app(tmp_path, NORMATTIVA_DB=str(db.with_name('normattiva.sqlite')))
    path = '/api/v1/ui/ricerca-legale/normativa/visualizza?atto=codice_procedura_civile&articolo=196'
    with app.test_client() as c:
        assert c.get(path).status_code == 401
        _login(c)
        r=c.get(path)
        assert r.status_code==200 and 'Testo vigente 196' in r.get_data(as_text=True)
        assert r.headers['Cache-Control']=='private, no-store'
        assert c.get(path+'&sha='+('0'*64)).status_code==409
        assert c.get(path.replace('196','99999')).status_code==404
        assert c.get('/api/v1/ui/ricerca-legale/normativa/visualizza?id=abc').status_code==400


def test_identita_esplicite_devono_concordare_anche_con_id(tmp_path):
    db = _biblioteca(tmp_path)
    r = risolvi(db, atto='codice_procedura_civile', articolo='196')
    assert risolvi(db, ident=r['id'], atto='codice_procedura_civile', url=r['source_url'])['text']==r['text']
    for args in ({'atto':'codice_civile'}, {'atto':'codice_procedura_civile','url':'https://example.test/altro'}):
        with pytest.raises(LookupError):risolvi(db,ident=r['id'],**args)


def test_riferimento_rettificato_apre_vecchio_testo_senza_ripromuoverlo(tmp_path):
    from lex.normativa.versioni_importazione import conserva_versione
    from lex.normativa.consultazione import dettaglio
    db = _biblioteca(tmp_path)
    old=risolvi(db,atto='codice_procedura_civile',articolo='196')
    with sqlite3.connect(db) as c:
        doc,xmlsha=c.execute('SELECT d.id,d.xml_sha256 FROM normative_documents d JOIN normative_articles a ON a.document_id=d.id WHERE a.id=?',(old['id'],)).fetchone()
        conserva_versione(c,document_id=doc,xml_sha256=xmlsha,revisione_parser='rettifica-test')
        c.execute('DELETE FROM normative_chunks WHERE article_id=?',(old['id'],))
        c.execute('DELETE FROM normative_articles WHERE id=?',(old['id'],))
    before=hashlib.sha256(db.read_bytes()).hexdigest()
    assert dettaglio(db,old['id']) is None
    archived=risolvi(db,ident=old['id'],sha=old['sha256'])
    assert archived['text']==old['text'] and archived['sha256']==old['sha256']
    assert archived['archived_import'] and archived['utilizzabile_come_fonte_corrente'] is False
    assert archived['article_url']==''
    assert 'non è utilizzabile come Fonte corrente' in documento_html(archived)
    assert hashlib.sha256(db.read_bytes()).hexdigest()==before
    with pytest.raises(LookupError):risolvi(db,ident=old['id'],atto='codice_civile')
    with sqlite3.connect(db) as c:
        c.execute("UPDATE normative_import_history SET snapshot_json=snapshot_json||' '")
    with pytest.raises(ValueError,match='alterato'):risolvi(db,ident=old['id'])


def test_url_non_puo_cambiare_articolo_allegato_o_edizione(tmp_path):
    db=_biblioteca(tmp_path)
    item=risolvi(db,atto='codice_procedura_civile',articolo='196')
    base='https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1940-10-28;1443'
    for url in (base+':1~art192',base+':2~art196',base+':1~art196!vig=1900-01-01'):
        with pytest.raises(LookupError):risolvi(db,ident=item['id'],atto='codice_procedura_civile',url=url)


def test_archivio_generale_con_urn_incompleto_usa_identita_tipizzata(tmp_path):
    from lex.normativa.consultazione import dettaglio
    db=_biblioteca(tmp_path)
    selected=risolvi(db,atto='codice_procedura_civile',articolo='196')
    with sqlite3.connect(db) as c:
        docid=c.execute('SELECT document_id FROM normative_articles WHERE id=?',(selected['id'],)).fetchone()[0]
        c.execute("UPDATE normative_documents SET urn='urn:',collection_name='Codici',numero='1443',data_atto='1940-10-28',xml_entry='REGIO DECRETO_19401028_1443/1940-10-28_040U1443_ORIGINALE_V0.xml' WHERE id=?",(docid,))
        c.execute("UPDATE normative_chunks SET metadata_json='{}' WHERE document_id=?",(docid,))
    item=dettaglio(db,selected['id'],includi_archivio_generale=True)
    assert item['urn']=='urn:nir:stato:regio.decreto:1940-10-28;1443'
    assert 'atto.codiceRedazionale=040U1443' in item['source_url']
    assert 'atto.dataPubblicazioneGazzetta=1940-10-28' in item['source_url']
    assert item['source_provenance']['urn_archiviato']=='urn:'


def test_numerazioni_native_non_sono_convertite_in_altri_articoli():
    assert numero_articolo('Art. 1.')=='1'
    assert numero_articolo('Art. 314/2.')=='314/2'
    assert numero_articolo('Art. XIX.')=='xix'
    assert numero_articolo('Art. I-bis.')=='ibis'
    assert numero_articolo('I')!=numero_articolo('1')
    for bad in ('1..','IIII','1/2/3','XIX,XX'):
        with pytest.raises(ValueError):numero_articolo(bad)


def test_lettura_per_id_romano_mostra_testo_senza_inventare_link(tmp_path):
    from io import StringIO
    from tests.test_normativa_akn_trasporto import XML,leggi
    from lex.normativa.normattiva_importer import ensure_schema,insert_document,insert_articles_and_chunks
    doc=leggi(XML.replace(b'Allegato 1-art. 71 bis',b'Accordo-art. XIX'))
    db=tmp_path/'normattiva.sqlite'
    with sqlite3.connect(db) as c:
        ensure_schema(c)
        docid=insert_document(c,doc,store_full_text=True)
        insert_articles_and_chunks(c,docid,doc,jsonl_file=StringIO(),max_chunk_chars=1800,only_relevant_articles=False,preserva_esistenti=True)
        ident=c.execute('SELECT id FROM normative_articles WHERE article_number=?',(doc.articles[1].article_number,)).fetchone()[0]
    item=risolvi(db,ident=ident,articolo='XIX')
    assert item['text']==doc.articles[1].article_text and item['article_url']==''


def test_data_visibile_del_lettore_in_formato_italiano():
    from web.services.normative_article_reader import documento_html
    item={"number":"1","act_label":"Fonte controllata","source_url":"https://www.normattiva.it/",
        "article_url":"","text":"Corpo controllato.","updated_at":"2026-10-26","sha256":"a"*64}
    html=documento_html(item)
    assert "26/10/2026" in html
    assert "2026-10-26" not in html
    item["updated_at"]="codice_non_datato"
    assert "da riscontrare" in documento_html(item)
    assert "codice_non_datato" not in documento_html(item)


def test_rettifica_stesso_id_riscontra_numero_e_testo_archiviato(tmp_path):
    from lex.normativa.versioni_importazione import conserva_versione
    from lex.normativa.consultazione import dettagli_precedenti
    db=_biblioteca(tmp_path)
    old=risolvi(db,atto='codice_procedura_civile',articolo='196')
    with sqlite3.connect(db) as c:
        docid,xmlsha=c.execute('SELECT d.id,d.xml_sha256 FROM normative_documents d JOIN normative_articles a ON a.document_id=d.id WHERE a.id=?',(old['id'],)).fetchone()
        conserva_versione(c,document_id=docid,xml_sha256=xmlsha,revisione_parser='riscontro-stesso-id')
        c.execute('UPDATE normative_articles SET article_text=? WHERE id=?',(old['text']+' Rettifica documentata.',old['id']))
    archived=dettagli_precedenti(db,old['id'],sha=old['sha256'])
    assert len(archived)==1
    assert archived[0]['rettifica_corrente']['text']==old['text']+' Rettifica documentata.'
    assert archived[0]['utilizzabile_come_fonte_corrente'] is False
