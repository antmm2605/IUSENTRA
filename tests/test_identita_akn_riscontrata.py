"""Suffissi solo con due riscontri, senza modificare il corpo normativo."""
import hashlib
from copy import deepcopy
import pytest
from lxml import etree
from lex.normativa.identita_akn_riscontrata import riscontra_suffisso
XML=b'''<akomaNtoso xmlns="http://docs.oasis-open.org/legaldocml/ns/akn/3.0"><act><meta><identification><FRBRWork><FRBRalias value="urn:nir:stato:legge:1861-08-04;408"/><FRBRalias value="eli/id/1862/02/07/061U9203/ORIGINAL"/><FRBRdate date="1861-08-04"/></FRBRWork><FRBRExpression><FRBRdate date="1861-08-05"/></FRBRExpression></identification><publication date="1862-02-07"/></meta><preface><docNumber>408 ter</docNumber><docDate date="1861-08-04"/></preface><body><article><num>Art. 1.</num><paragraph><content><p>Testo originale della disposizione.</p></content></paragraph></article></body></act></akomaNtoso>'''
CAT={'numeroAttoAlfanumerico':'408 ter','numeroAtto':'408','dataEmanazione':'1861-08-04T00:00:00Z','denominazioneAtto':'LEGGE','dataGU':'1862-02-07','codiceRedazionale':'061U9203'}
def run(raw=XML,row=None):
 return riscontra_suffisso(raw,xml_sha256=hashlib.sha256(raw).hexdigest(),catalogo=CAT if row is None else row,pagina_catalogo_sha256='a'*64)
def test_due_fonti_concordi_derivato_esplicito_corpo_e_originale_immutati():
 before=hashlib.sha256(XML).hexdigest();result=run()
 assert hashlib.sha256(XML).hexdigest()==before
 assert result.prova['xml_originale_sha256']==before
 assert result.prova['urn_dichiarato_originale'].endswith(';408')
 assert result.prova['urn_derivato_interno_non_alias_ufficiale'].endswith(';408ter')
 assert result.prova['identita_citazione']=='https://www.gazzettaufficiale.it/eli/id/1862/02/07/061U9203/sg'
 ns={'a':'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'}
 old=etree.fromstring(XML).find('a:act/a:body',ns);new=etree.fromstring(result.xml).find('a:act/a:body',ns)
 assert etree.tostring(old,method='c14n')==etree.tostring(new,method='c14n')
@pytest.mark.parametrize('field,value',[('numeroAttoAlfanumerico','408 quater'),('numeroAtto','409'),('dataEmanazione','1861-08-05'),('denominazioneAtto','REGIO DECRETO'),('dataGU','1862-02-08'),('codiceRedazionale','061U9204')])
def test_metadato_discordante_impedisce_derivazione(field,value):
 row=deepcopy(CAT);row[field]=value
 with pytest.raises(ValueError):run(row=row)
def test_numero_diverso_non_e_una_correzione_di_suffisso():
 with pytest.raises(ValueError):run(XML.replace(b';408',b';407'))
def test_alias_che_ha_gia_un_suffisso_non_viene_sovrascritto():
 with pytest.raises(ValueError):run(XML.replace(b';408',b';408bis'))
def test_sha_originale_discordante_non_normalizza():
 with pytest.raises(ValueError,match='Impronte'):
  riscontra_suffisso(XML,xml_sha256='0'*64,catalogo=CAT,pagina_catalogo_sha256='a'*64)

@pytest.mark.parametrize('numero,base,alfa', [('DCCCXXIX-bis','829','829 bis'),('1/B','1','1/B')])
def test_serie_romana_e_letterale_con_riscontri_primari(numero,base,alfa):
 raw=XML.replace(b';408',(';'+base).encode()).replace(b'408 ter',numero.encode())
 row=dict(CAT,numeroAtto=base,numeroAttoAlfanumerico=alfa)
 result=run(raw,row)
 assert result.prova['numero_riscontrato']==alfa
 assert result.prova['urn_dichiarato_originale'].endswith(';'+base)
 assert result.prova['identita_citazione'].endswith('/061U9203/sg')

@pytest.mark.parametrize('numero,alfa',[('DCCCXXIX-bis','830 bis'),('1/B','1 bis')])
def test_serie_distinte_non_si_confondono(numero,alfa):
 base='829' if numero.startswith('D') else '1'
 raw=XML.replace(b';408',(';'+base).encode()).replace(b'408 ter',numero.encode())
 with pytest.raises(ValueError):run(raw,dict(CAT,numeroAtto=base,numeroAttoAlfanumerico=alfa))


def pacchetto(tmp_path):
 import json
 from lex.normativa.normattiva_akn_importer import parse_akn
 from lex.normativa.biblioteca.fabbisogno import norm_articolo
 page=json.dumps({'listaAtti':[CAT]}).encode()
 (tmp_path/'catalogo.json').write_bytes(page);(tmp_path/'originale.xml').write_bytes(XML)
 normalized=riscontra_suffisso(XML,xml_sha256=hashlib.sha256(XML).hexdigest(),catalogo=CAT,pagina_catalogo_sha256=hashlib.sha256(page).hexdigest())
 entry='1862-02-07_061U9203_ORIGINALE_V0.xml'
 doc=parse_akn(normalized.xml,zip_path=tmp_path/'originale.xml',entry=entry,collection_name='Riscontro identita GU',analizza_pertinenza=False)
 a=doc.articles[0];proof=dict(normalized.prova,file_xml_originale='originale.xml',file_pagina_catalogo='catalogo.json',xml_entry=entry)
 return {'urn':proof['identita_citazione'],'url':proof['identita_citazione'],'data_atto':doc.data_atto,'titolo_atto':doc.titolo,'atto':'LEGGE 408 ter','articolo':norm_articolo(a.article_number),'testo':a.article_text,'rubrica':a.article_title or '', 'struttura_normativa':a.struttura_normativa,'consolidato_al':doc.redazione_id,'provenienza_integrazione':{'normalizzazione_identita':proof,'partizione_xml':a.partizione,'localizzatore_xml':a.localizzatore_xml,'sha256_payload_ufficiale':proof['xml_originale_sha256'],'versione_formale_dal':doc.redazione_id,'vigenza_richiesta':doc.redazione_id}}

def test_ricevuta_ha_riscontri_fisici_e_testo_identico(tmp_path):
 from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto
 row=pacchetto(tmp_path)
 checked=verifica_riga_pacchetto(tmp_path,row)
 assert checked['sha256_testo']==hashlib.sha256(row['testo'].encode()).hexdigest()
 assert checked['numero']=='408 ter'

@pytest.mark.parametrize('field,value',[('testo','Testo inventato che non compare nella fonte'),('articolo','2'),('atto','LEGGE 408 quater')])
def test_dichiarazione_diversa_dalla_fonte_non_importabile(tmp_path,field,value):
 from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto
 row=pacchetto(tmp_path);row[field]=value
 with pytest.raises(ValueError):verifica_riga_pacchetto(tmp_path,row)

def test_originale_cambiato_dopo_ricevuta_viene_riletto(tmp_path):
 from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto
 row=pacchetto(tmp_path)
 (tmp_path/'originale.xml').write_bytes(XML.replace(b'Testo originale',b'Testo alterato'))
 with pytest.raises(ValueError,match='Impronte'):verifica_riga_pacchetto(tmp_path,row)

def test_prova_fuori_pacchetto_non_viene_letta(tmp_path):
 from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto
 row=pacchetto(tmp_path)
 row['provenienza_integrazione']['normalizzazione_identita']['file_xml_originale']='../originale.xml'
 with pytest.raises(ValueError,match='Percorso prova'):verifica_riga_pacchetto(tmp_path,row)

def test_fine_intervallo_non_puo_essere_autodichiarata(tmp_path):
 from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto
 row=pacchetto(tmp_path);row['provenienza_integrazione']['versione_formale_al_escluso']='2011-02-10'
 with pytest.raises(ValueError,match='Fine intervallo priva'):verifica_riga_pacchetto(tmp_path,row)


def test_cache_importazione_riusa_parser_ma_non_nasconde_alterazioni(tmp_path,monkeypatch):
 from lex.normativa.identita_akn_riscontrata import verifica_riga_pacchetto,verifica_cache_riscontri_identita
 from lex.normativa import normattiva_akn_importer
 row=pacchetto(tmp_path);cache={};calls=[];native=normattiva_akn_importer.parse_akn
 def counted(*args,**kwargs):calls.append(1);return native(*args,**kwargs)
 monkeypatch.setattr(normattiva_akn_importer,'parse_akn',counted)
 verifica_riga_pacchetto(tmp_path,row,cache=cache)
 verifica_riga_pacchetto(tmp_path,row,cache=cache)
 assert len(calls)==1
 verifica_cache_riscontri_identita(cache)
 (tmp_path/'originale.xml').write_bytes(XML.replace(b'Testo originale',b'Testo alterato'))
 with pytest.raises(ValueError):verifica_riga_pacchetto(tmp_path,row,cache=cache)
 with pytest.raises(ValueError):verifica_cache_riscontri_identita(cache)
