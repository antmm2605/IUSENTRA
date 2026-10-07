"""Il CSV usa la cache nativa cifrata; prove su directory temporanea isolata."""
import tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from web.services import document_tools_cache as cache
from web.services.document_tools import DocumentToolError

class ExportCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        app=Flask(__name__);app.secret_key='controlled-cache-test-key'
        app.config['DOCUMENT_TOOLS_CACHE_ROOT']=self.temp.name
        self.context=app.app_context();self.context.push();self.addCleanup(self.context.pop)
        self.tenant=patch.object(cache,'tenant_corrente',return_value='studio-controlled-a').start()
        self.user=patch.object(cache,'utente_corrente_id',return_value='user-a').start()
        self.addCleanup(patch.stopall)
    def store(self):return cache.store_result(b'\xef\xbb\xbfTitolo;Data\r\nProva;07/10/2026\r\n','riepilogo.csv','text/csv;charset=utf-8')
    def test_roundtrip_content_and_encryption(self):
        token=self.store();data,name,mime=cache.read_result(token)
        self.assertEqual(name,'riepilogo.csv');self.assertEqual(mime,'text/csv;charset=utf-8')
        self.assertIn(b'07/10/2026',data)
        stored=list(Path(self.temp.name).rglob('*.cache'))
        self.assertEqual(len(stored),1);self.assertNotIn(b'Titolo',stored[0].read_bytes())
    def test_other_user_cannot_download(self):
        token=self.store();self.user.return_value='user-b'
        with self.assertRaises(DocumentToolError):cache.read_result(token)
    def test_other_tenant_cannot_download(self):
        token=self.store();self.tenant.return_value='studio-controlled-b'
        with self.assertRaises(DocumentToolError):cache.read_result(token)
    def test_modified_token_is_rejected(self):
        token=self.store()
        with self.assertRaises(DocumentToolError):cache.read_result(token[:-1]+('a' if token[-1]!='a' else 'b'))
    def test_expired_token_is_explicit(self):
        token=self.store()
        with patch('time.time',return_value=time.time()+cache.TTL+5):
            with self.assertRaisesRegex(DocumentToolError,'scaduta'):cache.read_result(token)
    def test_missing_copy_is_explicit(self):
        token=self.store()
        for p in Path(self.temp.name).rglob('*.cache'):p.unlink()
        with self.assertRaisesRegex(DocumentToolError,'non è più disponibile'):cache.read_result(token)
    def test_no_identity_fails_closed(self):
        self.tenant.return_value='default'
        with self.assertRaises(DocumentToolError):self.store()
        self.tenant.return_value='studio-controlled-a';self.user.return_value=''
        with self.assertRaises(DocumentToolError):self.store()
    def test_corrupted_copy_is_rejected(self):
        token=self.store()
        list(Path(self.temp.name).rglob('*.cache'))[0].write_bytes(b'corrupted')
        with self.assertRaises(DocumentToolError):cache.read_result(token)
    def test_cache_capacity_remains_enforced(self):
        with patch.object(cache,'MAX_CACHE_FILES',1):
            self.store()
            with self.assertRaisesRegex(DocumentToolError,'piena'):self.store()

if __name__=='__main__':unittest.main()