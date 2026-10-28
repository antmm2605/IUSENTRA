"""La data della consultazione non diventa la versione della norma."""
import json,sqlite3
from datetime import date
from lex.normativa.consultazione import importa_fonti
from lex.normativa.biblioteca.lettura import leggi_articoli
from lex.normativa.provenienza_edizione import riscontro_alla_data

def packet(tmp_path,*,name='uno',start='2000-01-01',end='2010-01-01',text='Il testo della disposizione originaria resta integralmente disponibile.'):
    p=tmp_path/name;(p/'atti').mkdir(parents=True)
    row={'chiave':'legge_1_2000','urn':'urn:nir:stato:legge:2000-01-01;1','atto':'Legge 1/2000','titolo_atto':'Legge di prova','articolo':'1','testo':text,'data_atto':'2000-01-01','url':'https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2000-01-01;1','consolidato_al':start,'provenienza_integrazione':{'vigenza_richiesta':start,'versione_formale_dal':start,'versione_formale_al_escluso':end,'catena_ufficiale_completa':True,'sha256_payload_ufficiale':'a'*64}}
    (p/'atti/legge.jsonl').write_text(json.dumps(row)+'\n');return p

def test_intervallo_consente_lettura_esatta_senza_fingere_edizione_alla_data(tmp_path):
    db=tmp_path/'norme.sqlite';importa_fonti(packet(tmp_path),db,'2026-10-26')
    result=leggi_articoli(db,[{'chiave':'legge_1_2000','articolo':'1','data_riferimento':'2005-06-15'}])
    assert result['lettura_completa'] is True
    assert result['articoli'][0]['provenienza_archivio']['redazione_id']=='2000-01-01'
    assert result['articoli'][0]['applicabilita_al_fascicolo']=='da_verificare'
    assert leggi_articoli(db,[{'chiave':'legge_1_2000','articolo':'1','data_riferimento':'2010-01-01'}])['lettura_completa'] is False
    assert leggi_articoli(db,[{'chiave':'legge_1_2000','articolo':'1','edizione':'2005-06-15'}])['lettura_completa'] is False

def test_metadati_strutturati_e_data_aggiornamento_separata(tmp_path):
    db=tmp_path/'norme.sqlite';importa_fonti(packet(tmp_path),db,'2026-10-26')
    with sqlite3.connect(db) as c:
        assert c.execute('SELECT redazione_id FROM normative_documents').fetchone()[0]=='2000-01-01'
        assert c.execute("SELECT json_type(metadata_json,'$.consultazione_fonte'),json_type(metadata_json,'$.consultazione_provenienza') FROM normative_chunks").fetchone()==('object','object')

def test_edizioni_sovrapposte_non_scelgono_arbitrariamente_un_testo(tmp_path):
    db=tmp_path/'norme.sqlite';importa_fonti(packet(tmp_path),db,'2026-10-26')
    importa_fonti(packet(tmp_path,name='due',start='2001-01-01',end='2011-01-01',text='Un testo discordante nello stesso intervallo va verificato.'),db,'2026-10-26')
    result=leggi_articoli(db,[{'chiave':'legge_1_2000','articolo':'1','data_riferimento':'2005-06-15'}])
    assert result['lettura_completa'] is False and result['articoli']==[]

def test_fotografia_documentata_non_si_prolunga_a_date_diverse():
    md={'sha256_akn':'a'*64,'vigenza_richiesta':'2026-10-26'}
    assert riscontro_alla_data(md,date(2026,10,26)) is True
    assert riscontro_alla_data(md,date(2026,10,27)) is None
    assert riscontro_alla_data({'vigenza':'VIGENTE'},date(2026,10,26)) is None

def test_intervallo_incoerente_non_diventa_copertura_confermata():
    md={'sha256_akn':'a'*64,'catena_ufficiale_completa':True,'versione_formale_dal':'2026-10-26','versione_formale_al_escluso':'2026-10-25'}
    assert riscontro_alla_data(md,date(2026,10,26)) is None


def test_riimportazione_stessa_fonte_non_duplica_il_testo_al_cambio_giorno(tmp_path):
    db=tmp_path/'norme.sqlite';p=packet(tmp_path)
    importa_fonti(p,db,'2026-10-26')
    with sqlite3.connect(db) as c:before=tuple(c.execute('SELECT (SELECT COUNT(*) FROM normative_documents),(SELECT COUNT(*) FROM normative_articles),(SELECT COUNT(*) FROM normative_chunks)').fetchone())
    report=importa_fonti(p,db,'2026-10-27')
    with sqlite3.connect(db) as c:after=tuple(c.execute('SELECT (SELECT COUNT(*) FROM normative_documents),(SELECT COUNT(*) FROM normative_articles),(SELECT COUNT(*) FROM normative_chunks)').fetchone())
    assert before==after
    assert report['new_articles']==0 and report['new_chunks']==0
