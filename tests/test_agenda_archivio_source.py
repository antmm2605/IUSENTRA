from copy import deepcopy
from types import SimpleNamespace

import unittest

from pct.registro_letture.fatti_repository import Fatto
from web.services.agenda_archivio_source import fonte_da_fatto


def case():
    fact=Fatto(categoria='data',campo='udienza',valore='2026-10-07T10:45',id='canon-test',tipo='documento',oggetto_id='doc-1',sha256='a'*64,verifica='verificata')
    obj=SimpleNamespace(presente=True,impronta='a'*64,sha256_archivio='b'*64,nome='Ordinanza')
    doc=SimpleNamespace(id='doc-1',hash_sha256='b'*64,hash_contenuto_sha256='',nome='Ordinanza',eliminato_il='')
    event={'id':'agenda-1','start':'2026-10-07T10:45','technicalNotes':'ARCHIVIO_FATTO:canon-test\nFonte: documento:old-pec'}
    fasc=SimpleNamespace(id='case-1',documenti=[doc])
    class Registry:
        def fatti(self,tenant,fid,**filters):
            assert tenant=='tenant-1' and fid=='case-1'
            return [fact]
        def oggetto(self,tenant,fid,tipo,oid):
            assert (tenant,fid,tipo,oid)==('tenant-1','case-1','documento','doc-1')
            return obj
    return event,fasc,Registry(),fact,obj,doc


def source(case):
    return fonte_da_fatto(case[0],case[1],registro=case[2],tenant='tenant-1')


def check_current_fact_replaces_old_source_without_changing_appointment(case):
    before=deepcopy(case[0])
    result=source(case)
    assert result['sourceHref']=='/fascicoli/case-1/documenti/doc-1/visualizza'
    assert result['sourceVerified'] is True
    assert case[0]==before


def check_source_is_not_verified_when_evidence_does_not_support_it(case,change):
    event,fasc,registry,fact,obj,doc=case
    if change=='unverified':fact.verifica='plausibile'
    elif change=='different_time':event['start']='2026-10-07T14:00'
    elif change=='removed':obj.presente=False
    elif change=='changed_content':obj.impronta='c'*64
    elif change=='changed_storage':doc.hash_sha256='c'*64
    elif change=='no_document':fasc.documenti=[]
    elif change=='unknown_fact':event['technicalNotes']='ARCHIVIO_FATTO:unknown'
    result=source(case)
    assert result['sourceVerified'] is False
    assert result['sourceHref']==''


def check_manual_appointment_does_not_gain_an_inferred_source(case):
    case[0]['technicalNotes']='Appuntamento inserito dall’avvocato'
    assert source(case)=={}


class SourceTests(unittest.TestCase):
    def test_current_source_preserves_appointment(self):
        check_current_fact_replaces_old_source_without_changing_appointment(case())

    def test_invalid_evidence_is_never_verified(self):
        for change in ['unverified','different_time','removed','changed_content','changed_storage','no_document','unknown_fact']:
            with self.subTest(change=change):
                check_source_is_not_verified_when_evidence_does_not_support_it(case(),change)

    def test_manual_appointment(self):
        check_manual_appointment_does_not_gain_an_inferred_source(case())


if __name__=='__main__':unittest.main()
