import hashlib
import pytest
from lex.normativa.applicabilita import Applicabilita
from lex.retrieval.selezione_fonti import leggi_scelta, prepara_fonti, Scelta

def candidate(text):
    return {"testo":text,"riferimento":{"atto":"fixture","articolo":"1",
        "provenienza":{"tipo":"norma","url":"https://example.org/fixture","versione":"test",
                        "acquisita_il":"25/10/2026","sha256":hashlib.sha256(text.encode()).hexdigest()}}}

def prepare(candidates, choice=Scelta((),()), required=None, **kw):
    proof={i:Applicabilita("applicabile",("fixture",)) for i in range(1,len(candidates)+1)}
    return prepara_fonti(candidates,choice,proof,required or set(),tokenizza=len,budget_token=20000,**kw)

def test_strict_json_no_digits_extracted_from_prose():
    with pytest.raises(ValueError):leggi_scelta('Articolo2932: scegli1e2',50)
    with pytest.raises(ValueError):leggi_scelta('{"scelti":[1],"approvato":true}',50)
    result=leggi_scelta('{"scelti":[true,0,-1,51,"2",2,2,3]}',50)
    assert result.accettati==(2,3) and len(result.scartati)==6

def test_selection_is_priority_and_empty_choice_keeps_retrieval():
    c=[candidate('uno'),candidate('due'),candidate('tre')]
    assert [x['n'] for x in prepare(c,Scelta((3,),()))['fonti']]==[3,1,2]
    assert [x['n'] for x in prepare(c)['fonti']]==[1,2,3]

def test_changed_text_never_enters_prompt():
    c=candidate('originale');c['testo']='alterato'
    result=prepare([c],required={1})
    assert not result['pronto_per_modello'] and result['fonti']==[]

def test_unknown_applicability_does_not_become_source():
    result=prepara_fonti([candidate('uno')],Scelta((1,),()),{},set(),tokenizza=len,budget_token=10000)
    assert not result['pronto_per_modello'] and result['fonti']==[]

def test_budget_does_not_truncate_required_legal_text():
    c=[candidate('a'*2000)]
    result=prepara_fonti(c,Scelta((1,),()),{1:Applicabilita('applicabile',())},{1},tokenizza=len,budget_token=500)
    assert result['fonti']==[] and not result['pronto_per_modello']
    assert c[0]['testo']=='a'*2000

def test_case_context_is_part_of_budget_and_sources_remain_whole():
    c=[candidate('testo integrale')]
    result=prepare(c,contesto='Parte assistita: convenuto; richiesta: difendersi')
    assert result['fonti'][0]['testo']=='testo integrale' and result['pronto_per_modello']
    result=prepara_fonti(c,Scelta((),()),{1:Applicabilita('applicabile',())},set(),tokenizza=len,budget_token=5,contesto='caso lungo')
    assert not result['pronto_per_modello']
