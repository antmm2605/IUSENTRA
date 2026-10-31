from collections import Counter

import pytest

from integrations.traduzione_locale import client


@pytest.mark.parametrize('text',["Texte court.","  Première phrase. Deuxième phrase. "*100,"A"*2000,"Mot\n"*500])
def test_segmentation_preserves_every_original_character_without_truncation(text):
    parts=client.segmenti(text)
    assert ''.join(text[p['inizio']:p['fine']] for p in parts)==text
    assert all(0<p['fine']-p['inizio']<=650 for p in parts)
    assert all(client.digest(text[p['inizio']:p['fine']])==p['sha256'] for p in parts)


def test_reference_placeholders_roundtrip_without_changing_legal_identifiers():
    text='Article 4 TUE, article 6 TFUE, C‑521/25, 2002/90/CE, ECLI:EU:C:2026:875 et TUE.'
    protected,refs=client.protect_references(text)
    assert 'TUE' not in protected and 'TFUE' not in protected
    assert client.restore_references(protected,refs)==text
    assert Counter(refs.values())['TUE']==2
    with pytest.raises(ValueError):client.restore_references(protected.replace(next(iter(refs)),''),refs)
    with pytest.raises(ValueError):client.restore_references(protected+next(iter(refs)),refs)


def test_placeholder_prefix_cannot_collide_with_source_text():
    text='ZXQREF0001ZXQ est littéral, mais TUE est une référence.'
    protected,refs=client.protect_references(text)
    assert client.restore_references(protected,refs)==text


@pytest.mark.parametrize('models',[{'data':[]},{'data':[{'id':'other-model'}]}])
def test_model_identity_is_checked_before_translation(monkeypatch,models):
    calls=[]
    def call(_config,method,path,payload=None):calls.append(path);return models
    monkeypatch.setattr(client,'call',call)
    with pytest.raises(ValueError):client.rpc({},'traduci',{'testo':'Texte','lingua':'fr','sha256_modello':client.MODEL['sha256_modello']})
    assert calls==['/v1/models']


@pytest.mark.parametrize('reason',['length','error','tool_calls'])
def test_incomplete_generation_is_not_accepted(monkeypatch,reason):
    def call(_config,method,path,payload=None):
        return {'data':[{'id':client.ALIAS}]} if path=='/v1/models' else {'choices':[{'finish_reason':reason,'message':{'content':'test'}}]}
    monkeypatch.setattr(client,'call',call)
    with pytest.raises(ValueError):client.rpc({},'traduci',{'testo':'Texte','lingua':'fr','sha256_modello':client.MODEL['sha256_modello']})


def test_altered_source_reference_is_rejected_and_original_remains_intact(monkeypatch):
    text='Article 4 TUE.'
    def call(_config,method,path,payload=None):
        return {'data':[{'id':client.ALIAS}]} if path=='/v1/models' else {'choices':[{'finish_reason':'stop','message':{'content':'Articolo 4 TFUE.'}}]}
    monkeypatch.setattr(client,'call',call)
    with pytest.raises(ValueError):client.rpc({},'traduci',{'testo':text,'lingua':'fr','sha256_modello':client.MODEL['sha256_modello']})
    assert text=='Article 4 TUE.'


def test_numeric_discrepancy_is_explicit_not_silently_corrected(monkeypatch):
    def call(_config,method,path,payload=None):
        return {'data':[{'id':client.ALIAS}]} if path=='/v1/models' else {'choices':[{'finish_reason':'stop','message':{'content':'Termine di 60 giorni.'}}]}
    monkeypatch.setattr(client,'call',call)
    result=client.rpc({},'traduci',{'testo':'Délai de 30 jours.','lingua':'fr','sha256_modello':client.MODEL['sha256_modello']})
    assert result['avvisi'] and '60' in result['testo']
