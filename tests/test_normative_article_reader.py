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
