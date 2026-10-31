import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from pct.traduzioni_giurisprudenza import TraduzioniCorpus
from web.services import giurisprudenza_translation as service


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


@pytest.fixture
def source(tmp_path):
    path=tmp_path/"corpus.db"
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE sentenze(id INTEGER PRIMARY KEY)")
        c.execute("INSERT INTO sentenze VALUES(1)")
    record={"id":1,"titolo":"Fonte francese","testo_integrale":"Texte un. Texte deux.","documenti":[{"lingua":"fr","valido":True}]}
    owner=SimpleNamespace(db_path=str(path),get_sentenza=lambda sid:record.copy() if sid==1 else None)
    return owner,record


@pytest.fixture
def calls(monkeypatch):
    calls=[]
    metadata={"modello":"modello-test","revisione":"pinned","sha256_modello":"a"*64,"motore":"motore-test"}
    def rpc(config,action,payload):
        calls.append(action)
        text=payload['testo']
        if action=='prepara':
            return {**metadata,"sha256_originale":sha(text),"segmenti":[{"inizio":0,"fine":10,"sha256":sha(text[:10])},{"inizio":10,"fine":len(text),"sha256":sha(text[10:])}]}
        translated='Traduzione di '+text
        return {**metadata,"sha256_originale":sha(text),"testo":translated,"sha256_traduzione":sha(translated),"avvisi":[]}
    monkeypatch.setattr(service,'rpc',rpc)
    return calls


def test_translation_is_incremental_complete_and_reused_without_inference(source,calls):
    owner,_record=source
    first=service.start(owner,{},1,'fr')
    assert first['stato']=='in_attesa' and first['totale']==2
    assert service.step(owner,{},1,first['id'])['completati']==1
    assert service.step(owner,{},1,first['id'])['stato']=='completa'
    assert len(service.document(owner,1,first['id'])['parti'])==2
    before=list(calls)
    assert service.start(owner,{},1,'fr')['id']==first['id']
    assert service.step(owner,{},1,first['id'])['stato']=='completa'
    assert calls==before==['prepara','traduci','traduci']


def test_changed_source_creates_new_version_and_old_is_not_current(source,calls):
    owner,record=source
    first=service.start(owner,{},1,'fr')
    service.step(owner,{},1,first['id']);service.step(owner,{},1,first['id'])
    record['testo_integrale']='Autre un. Autre deux.'
    with pytest.raises(ValueError):service.document(owner,1,first['id'])
    second=service.start(owner,{},1,'fr')
    assert second['id']!=first['id']
    assert TraduzioniCorpus(owner.db_path).get(1,first['id'])['stato']=='completa'


def test_partial_translation_cannot_be_presented_as_complete(source,calls):
    owner,_=source;job=service.start(owner,{},1,'fr');service.step(owner,{},1,job['id'])
    with pytest.raises(ValueError):service.document(owner,1,job['id'])


def test_parallel_claims_cannot_translate_same_segment_twice(source,calls):
    owner,_=source;job=service.start(owner,{},1,'fr')
    def claim():return TraduzioniCorpus(owner.db_path).claim(1,job['id'])
    with ThreadPoolExecutor(max_workers=2) as pool:parts=list(pool.map(lambda _:claim(),range(2)))
    assert sum(p is not None for p in parts)==1


def test_same_identifiers_in_other_studio_do_not_expose_translation(source,calls,tmp_path):
    owner,record=source;job=service.start(owner,{},1,'fr')
    other=tmp_path/'other.db'
    with sqlite3.connect(other) as c:c.execute('CREATE TABLE sentenze(id INTEGER PRIMARY KEY)');c.execute('INSERT INTO sentenze VALUES(1)')
    foreign=SimpleNamespace(db_path=str(other),get_sentenza=lambda _:record.copy())
    with pytest.raises(KeyError):service.status(foreign,1,job['id'])
    with pytest.raises(KeyError):TraduzioniCorpus(owner.db_path).get(2,job['id'])


def test_failed_step_is_not_retried_without_explicit_user_action(source,calls,monkeypatch):
    owner,_=source;job=service.start(owner,{},1,'fr');service.step(owner,{},1,job['id'])
    working=service.rpc
    def fail(*_args):raise OSError('synthetic failure')
    monkeypatch.setattr(service,'rpc',fail)
    with pytest.raises(ValueError):service.step(owner,{},1,job['id'])
    assert service.start(owner,{},1,'fr')['stato']=='errore'
    monkeypatch.setattr(service,'rpc',working)
    resumed=service.start(owner,{},1,'fr',retry=True)
    assert resumed['completati']==1
    assert service.step(owner,{},1,job['id'])['stato']=='completa'
    assert calls.count('traduci')==2


def test_translation_output_tampering_fails_reader(source,calls):
    owner,_=source;job=service.start(owner,{},1,'fr');service.step(owner,{},1,job['id']);service.step(owner,{},1,job['id'])
    with sqlite3.connect(owner.db_path) as c:c.execute("UPDATE corpus_traduzioni_segmenti SET testo_tradotto='changed'")
    with pytest.raises(ValueError):service.document(owner,1,job['id'])


def test_language_is_checked_against_stored_source_not_browser(source,calls):
    owner,_=source
    for language in ['en','it','xx','fr;command']:
        with pytest.raises(ValueError):service.start(owner,{},1,language)
    assert calls==[]


def test_sql_cache_does_not_store_json_payloads_or_modify_original(source,calls):
    owner,record=source;before=record.copy();service.start(owner,{},1,'fr')
    with sqlite3.connect(owner.db_path) as c:
        for table in ['corpus_traduzioni','corpus_traduzioni_segmenti','corpus_traduzioni_eventi']:
            assert all('json' not in row[1].lower() for row in c.execute('pragma table_info('+table+')'))
    assert record==before
