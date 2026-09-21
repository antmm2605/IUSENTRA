"""Small contracts: current IDs, protected edits, pure state requests."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from pathlib import Path
from web.services.rettifiche_letture_storiche import pianifica_rettifiche, NOTA_TERMINE_STORICO
from web.services.catalogo_archivio_runtime import prepara_catalogo
from pct.document_intelligence.sources import source_from_fascicolo_document
from pct.registro_letture import Oggetto
from web.services.document_intelligence_runtime import build_lex_indexing_summary_payload


class ReadingArchiveConsistencyTests(unittest.TestCase):
    def test_legacy_deadline_requires_current_contract_and_matching_start(self):
        quote = 'Contratto di lavoro a tempo determinato, con decorrenza dal 01/09/2025 e cessazione al 30/06/2026 per diciotto ore settimanali.'
        fact = NS(id='fact-1', tipo='documento', oggetto_id='doc-1', sha256='sha-1', campo='natura_documentale', categoria='documento', valore='contratto_lavoro', verifica='verificata')
        obj = NS(tipo='documento', oggetto_id='doc-1', impronta='sha-1')
        deadline = NS(id='deadline', data_scadenza='2025-09-01', stato='APERTO', note=NOTA_TERMINE_STORICO, titolo='Termine del 01/09/2025', descrizione=quote)
        args = dict(fatti=[fact], oggetti=[obj], scadenze=[deadline], testi={'doc-1': quote})
        case = NS(attivita=[])
        self.assertEqual(len(pianifica_rettifiche(case, **args)), 1)
        deadline.note += ' Confermata dal professionista.'
        self.assertEqual(pianifica_rettifiche(case, **args), [])
        deadline.note = NOTA_TERMINE_STORICO
        obj.impronta = 'new-sha'
        self.assertEqual(pianifica_rettifiche(case, **args), [])
        obj.impronta = 'sha-1'
        deadline.data_scadenza = '2025-09-02'; deadline.titolo = 'Termine del 02/09/2025'
        self.assertEqual(pianifica_rettifiche(case, **args), [])

    def test_catalog_uses_current_original_id_and_ignores_historical_sha(self):
        def record(id, sha, date):
            return NS(id=id, sha256=sha, status='ready', current_version_id='version-'+id, updated_at=date, original_filename='Ricorso.pdf', safe_filename='Ricorso.pdf', file_type='pdf', mime_type='application/pdf', size_bytes=100)
        repository = Mock()
        repository.list_documents.return_value = [record('history','old-sha','2026-09-21'),record('new-record','current-sha','2026-09-20'),record('old-record','current-sha','2026-09-19')]
        repository.list_catalog_assignments.return_value = []
        repository.get_extracted_text.return_value = NS(text='Ricorso con testo corrente', extraction_engine='pdf-inspector')
        case = NS(id='case-1', documenti=[NS(id='original-id', nome='Ricorso.pdf')])
        objects = [Oggetto(oggetto_id='original-id', tipo='documento', presente=True, sha256='', sha256_archivio='current-sha')]
        with patch('web.services.catalogo_archivio_runtime.fascicolo_catalog_context',return_value={}), patch('web.services.catalogo_archivio_runtime.resolve_profile',return_value=('',None)):
            sources, texts, report = prepara_catalogo(case,objects,repository,'tenant-a')
        self.assertEqual([s.source_id for s in sources], ['original-id'])
        self.assertEqual(sources[0].metadata['document_ai_id'], 'new-record')
        repository.get_extracted_text.assert_called_once_with('tenant-a','case-1','new-record','version-new-record')
        self.assertEqual(report['file_reads'],0)
        self.assertEqual(set(texts),{'original-id'})

    def test_state_source_does_not_open_encrypted_file_for_unknown_hash(self):
        document = NS(id='doc',nome='Ricorso.pdf',percorso='case/ricorso.pdf',hash_sha256='cipher-hash')
        decrypt = Mock(side_effect=AssertionError('GET attempted decryption'))
        with patch.object(Path,'exists',side_effect=AssertionError('GET attempted filesystem inventory')), patch.object(Path,'read_bytes',side_effect=AssertionError('GET opened bytes')):
            source = source_from_fascicolo_document(tenant_id='tenant',fascicolo_id='case',document=document,documents_root='/data',decrypt=decrypt,allow_content_read=False)
        self.assertIsNotNone(source)
        decrypt.assert_not_called()

    def test_index_get_never_registers_or_processes(self):
        service = Mock(); service.build_lex_indexing_summary.return_value.to_dict.return_value = {'ready':1}
        target='web.services.document_intelligence_runtime.'
        with patch(target+'assert_document_ai_fascicolo_current_tenant'), patch(target+'document_ai_tenant_id',return_value='tenant'), patch(target+'build_document_ai_service',return_value=service), patch(target+'collect_document_ai_sources_for_fascicolo',return_value=[]) as collect, patch(target+'_registro_indice_documentale',side_effect=AssertionError('GET writes registry')):
            self.assertEqual(build_lex_indexing_summary_payload('case',process=False,user_context={}),{'ready':1})
        collect.assert_called_once_with('case',tenant_id='tenant',allow_content_read=False)
        service.process_lex_indexing_sources.assert_not_called()


if __name__ == '__main__':
    unittest.main()
