"""Il piano AI non approva regole e non sceglie l'evento temporale del filtro."""
import hashlib,json
from copy import deepcopy
import pytest
from lex.normativa.applicabilita import impronta
from lex.normativa.regole_applicabilita import carica_registro,valuta_fonte_registrata
ACT='urn:nir:stato:legge:2020-01-01;7'
TEXT='Nel caso di prova la disposizione si applica dal primo gennaio 2027.'
def regola(esito='non_applicabile'):
 return {'atto_id':ACT,'ambito':'processuale','evento':'instaurazione_procedimento','dal':None if esito=='non_applicabile' else '2027-01-01','al_escluso':'2027-01-01' if esito=='non_applicabile' else None,'esito':esito,'fonte':{'testo':TEXT,'url':'https://www.normattiva.it/uri-res/N2Ls?'+ACT,'versione':'2026-10-26','acquisita_il':'2026-10-26','sha256':hashlib.sha256(TEXT.encode()).hexdigest(),'estratto':'dal primo gennaio 2027'}}
def installa(tmp_path,monkeypatch,rules,approved=True):
 obj={'schema':1,'regole':rules,'approvazioni':[{'regola_sha256':impronta(r),'approvata_da':'Revisore di prova','approvata_il':'2026-10-26','riferimento_approvazione':'solo fixture del test'} for r in rules] if approved else []}
 raw=json.dumps(obj).encode();p=tmp_path/'regole.json';p.write_bytes(raw)
 monkeypatch.setenv('PCT_NORMATTIVA_APPLICABILITA_MANIFEST',str(p));monkeypatch.setenv('PCT_NORMATTIVA_APPLICABILITA_MANIFEST_SHA256',hashlib.sha256(raw).hexdigest())
 return p

def eventi(day='2026-10-26',confirmed=True):
 return {'instaurazione_procedimento':{'data':day,'confermato':confirmed,'fonte_sha256':'b'*64}}

def test_senza_registro_nessuna_regola_approvata_implicita(monkeypatch):
 monkeypatch.delenv('PCT_NORMATTIVA_APPLICABILITA_MANIFEST',raising=False);monkeypatch.delenv('PCT_NORMATTIVA_APPLICABILITA_MANIFEST_SHA256',raising=False)
 r=valuta_fonte_registrata(ACT,{},eventi(),carica_registro())
 assert r['stato']=='da_verificare' and not r['regole_pertinenti']

def test_approvazione_assente_non_diventa_filtro(tmp_path,monkeypatch):
 installa(tmp_path,monkeypatch,[regola()],approved=False)
 r=valuta_fonte_registrata(ACT,{},eventi(),carica_registro())
 assert r['stato']=='da_verificare' and 'non approvata' in ' '.join(r['motivi'])

def test_regola_approvata_usa_evento_confermato_fisso(tmp_path,monkeypatch):
 rule=regola();installa(tmp_path,monkeypatch,[rule]);registry=carica_registro()
 r=valuta_fonte_registrata(ACT,{},eventi(),registry,riscontra_fonte=lambda *_:True)
 assert r['stato']=='non_applicabile' and r['regole']==[impronta(rule)]
 assert r['registro_sha256']==registry.sha256

@pytest.mark.parametrize('ev',[{},eventi(confirmed=False),{'altro_evento':eventi()['instaurazione_procedimento']}])
def test_eventi_mancanti_non_escludono_o_applicano_norme(tmp_path,monkeypatch,ev):
 installa(tmp_path,monkeypatch,[regola()])
 assert valuta_fonte_registrata(ACT,{},ev,carica_registro())['stato']=='da_verificare'

def test_regola_positiva_non_scavalca_copertura_edizione(tmp_path,monkeypatch):
 installa(tmp_path,monkeypatch,[regola('applicabile')]);registry=carica_registro()
 assert valuta_fonte_registrata(ACT,{},eventi('2027-01-02'),registry,riscontra_fonte=lambda *_:True)['stato']=='da_verificare'
 proof={'edizione_archiviata':{'vigenza_richiesta':'2027-01-02','xml_sha256':'c'*64}}
 assert valuta_fonte_registrata(ACT,proof,eventi('2027-01-02'),registry,riscontra_fonte=lambda *_:True)['stato']=='applicabile'
 assert valuta_fonte_registrata(ACT,proof,eventi('2027-01-03'),registry,riscontra_fonte=lambda *_:True)['stato']=='da_verificare'

def test_stesso_numero_con_data_diversa_non_e_lo_stesso_atto(tmp_path,monkeypatch):
 installa(tmp_path,monkeypatch,[regola()])
 result=valuta_fonte_registrata(ACT.replace('01-01','02-01'),{},eventi(),carica_registro())
 assert not result['regole_pertinenti'] and result['stato']=='da_verificare'

def test_registro_alterato_non_e_letto(tmp_path,monkeypatch):
 p=installa(tmp_path,monkeypatch,[regola()]);p.write_text('{}')
 with pytest.raises(ValueError,match='alterato'):carica_registro()

def test_approvazione_di_vecchia_impronta_non_approva_regola_cambiata(tmp_path,monkeypatch):
 p=installa(tmp_path,monkeypatch,[regola()]);o=json.loads(p.read_text());o['regole'][0]['al_escluso']='2028-01-01';raw=json.dumps(o).encode();p.write_bytes(raw)
 monkeypatch.setenv('PCT_NORMATTIVA_APPLICABILITA_MANIFEST_SHA256',hashlib.sha256(raw).hexdigest())
 with pytest.raises(ValueError,match='non riferibile'):carica_registro()


def test_regola_approvata_senza_riscontro_primario_non_filtra(tmp_path,monkeypatch):
 installa(tmp_path,monkeypatch,[regola()])
 assert valuta_fonte_registrata(ACT,{},eventi(),carica_registro())['stato']=='da_verificare'


def fonte_cache(tmp_path,monkeypatch):
 import sqlite3,zipfile
 from datetime import date
 from lex.normativa.versioni_akn import importa_multiversione,leggi_versione
 from lex.testi_ufficiali import collegamento_normattiva
 monkeypatch.delenv('PCT_NORMATTIVA_LETTORI_MANIFEST',raising=False);monkeypatch.delenv('PCT_NORMATTIVA_LETTORI_MANIFEST_SHA256',raising=False)
 xml=b'<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act><meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:2020-01-01;7"/><FRBRdate date="2020-01-01"/></FRBRWork><FRBRExpression><FRBRdate date="2020-01-02"/></FRBRExpression></identification></meta><body><article><num>Art. 1.</num><paragraph><content><p>Corpo normativo della disposizione transitoria da leggere integralmente.</p></content></paragraph></article></body></act></akomaNtoso>'
 archive=tmp_path/'fonte.zip'
 with zipfile.ZipFile(archive,'w') as z:z.writestr('2020-01-01_20G00007_ORIGINALE_V0.xml',xml)
 db=tmp_path/'cache.sqlite'
 with sqlite3.connect(db) as conn:
  report=importa_multiversione(conn,archivio=archive,sha256_atteso=hashlib.sha256(archive.read_bytes()).hexdigest(),acquisita_utc='2027-01-04T10:00:00+00:00')
  assert report['errori']==[]
  row=leggi_versione(conn,urn=ACT,data_riferimento='2027-01-02')[0]
 fields=('urn','numero','partizione','localizzatore_xml','versione_dal','versione_al_escluso','espressione_dal','xml_sha256','xml_decodificato_sha256','zip_sha256','acquisita_utc','lettore_sha256','lettore_riscontro_sha256','rilettura_catena_sha256','politica_lettori_sha256','rapporto_compatibilita_sha256')
 proof={'versione':row['espressione_dal'],'acquisita_il':'2027-01-04','archivio':'cache_akn','urn':ACT,'articolo':'1','testo':row['testo'],'sha256':hashlib.sha256(row['testo'].encode()).hexdigest(),'url':collegamento_normattiva(ACT,'1'),'edizione_archiviata':{k:row.get(k) for k in fields}}
 return db,proof,date(2027,1,2)


def test_riscontro_reale_cache_stesso_testo_altra_provenienza_decade(tmp_path,monkeypatch):
 import sqlite3
 from lex.normativa.regole_applicabilita import riscontro_fonte_cache
 db,proof,day=fonte_cache(tmp_path,monkeypatch)
 assert riscontro_fonte_cache(proof,day,db) is True
 with sqlite3.connect(db) as conn:conn.execute("UPDATE normative_akn_chains SET acquisita_utc='2027-01-04T11:00:00+00:00'")
 assert riscontro_fonte_cache(proof,day,db) is False


def test_testo_della_cache_alterato_non_viene_ignorato(tmp_path,monkeypatch):
 import sqlite3
 from lex.normativa.regole_applicabilita import riscontro_fonte_cache
 db,proof,day=fonte_cache(tmp_path,monkeypatch)
 with sqlite3.connect(db) as conn:conn.execute('UPDATE normative_akn_articles SET testo=?',('Corpo alterato',))
 with pytest.raises(ValueError,match='alterato'):riscontro_fonte_cache(proof,day,db)


def test_regola_di_articolo_non_esclude_intero_codice(tmp_path,monkeypatch):
 rule=dict(regola(),articoli=['390']);installa(tmp_path,monkeypatch,[rule]);registry=carica_registro()
 yes=valuta_fonte_registrata(ACT,{},eventi(),registry,articolo='390',riscontra_fonte=lambda *_:True)
 no=valuta_fonte_registrata(ACT,{},eventi(),registry,articolo='391',riscontra_fonte=lambda *_:True)
 assert yes['stato']=='non_applicabile'
 assert no['stato']=='da_verificare' and not no['regole_pertinenti']


def test_una_fonte_congiunta_non_riscontrata_impedisce_il_filtro(tmp_path,monkeypatch):
 rule=regola();other=dict(rule['fonte'],versione='altra disposizione');rule['fonti_congiunte']=[other]
 installa(tmp_path,monkeypatch,[rule]);registry=carica_registro()
 result=valuta_fonte_registrata(ACT,{},eventi(),registry,riscontra_fonte=lambda f,_: f is not registry.regole[0]['fonti_congiunte'][0])
 assert result['stato']=='da_verificare'


def test_partizione_non_specificata_non_viene_indovinata(tmp_path,monkeypatch):
 rule=dict(regola(),partizione_xml='allegato_1');installa(tmp_path,monkeypatch,[rule])
 result=valuta_fonte_registrata(ACT,{},eventi(),carica_registro(),riscontra_fonte=lambda *_:True)
 assert result['stato']=='da_verificare' and 'partizione' in ' '.join(result['motivi'])


def test_scheda_non_applicabile_si_ferma_prima_del_modello(tmp_path,monkeypatch):
 from datetime import date
 from lex.normativa.biblioteca.ricerca_fonti import integra_fonti
 from lex.procedura_atti.fonti_scheda import FontiScheda
 from lex.normativa import regole_applicabilita as registro
 installa(tmp_path,monkeypatch,[regola()]);monkeypatch.setattr(registro,'riscontro_fonte_cache',lambda *_:True)
 fonti=FontiScheda('SCHEMA','Schema di prova',fonti={1:TEXT},fonti_ref=[{'n':1,'atto':ACT,'articolo':'1','provenienza':{'url':'https://www.normattiva.it/uri-res/N2Ls?'+ACT}}])
 def forbidden(*_):raise AssertionError('Il modello non deve essere chiamato con la base non applicabile')
 with pytest.raises(ValueError,match='non applicabile'):
  integra_fonti(fonti,richiesta='Atto di prova',fatti='Fatti controllati',biblioteca=tmp_path/'non-aperto.sqlite',chiama_modello=forbidden,oggi=date(2026,10,26),eventi=eventi())
 assert not (tmp_path/'non-aperto.sqlite').exists()


def test_regola_non_approvata_non_esclude_la_scheda(tmp_path,monkeypatch):
 from datetime import date
 from lex.normativa.biblioteca.ricerca_fonti import integra_fonti
 from lex.procedura_atti.fonti_scheda import FontiScheda
 installa(tmp_path,monkeypatch,[regola()],approved=False)
 fonti=FontiScheda('SCHEMA','Schema di prova',fonti={1:TEXT},fonti_ref=[{'n':1,'atto':ACT,'articolo':'1','provenienza':{'url':'https://www.normattiva.it/uri-res/N2Ls?'+ACT}}])
 class ArrivatoAlModello(Exception):pass
 def reached(*_):raise ArrivatoAlModello()
 with pytest.raises(ArrivatoAlModello):
  integra_fonti(fonti,richiesta='Atto di prova',fatti='Fatti controllati',biblioteca=tmp_path/'non-aperto.sqlite',chiama_modello=reached,oggi=date(2026,10,26),eventi=eventi())
 assert any('non approvata' in p for p in fonti.pendenze)
