import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.service import DocumentAIService

class ReacquireTests(unittest.TestCase):
    def test_sql_version_switch_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder:
            repo = DocumentAIRepository.from_sqlite_db(Path(folder)/"studio.db", storage_root=Path(folder)/"blobs")
            service = DocumentAIService(repo)
            context = {"skip_permission_check": True, "user_id": "controlled-test"}
            upload = io.BytesIO(b"original document")
            upload.filename = "source.txt"
            upload.content_type = "text/plain"
            extract = ExtractionResult(ok=True, text="Original extracted text", pages=[], extraction_engine="test")
            with patch("pct.document_intelligence.service.extract_text_from_document", return_value=extract):
                original = service.upload_document_for_fascicolo("tenant", "case", upload, context).document
                old_id = original.current_version_id
                with patch.object(repo, "save_extracted_text", side_effect=RuntimeError("forced SQL failure")):
                    with self.assertRaisesRegex(RuntimeError, "forced SQL failure"):
                        service.reacquire_existing_version("tenant", "case", original.id, b"original document", context)
                self.assertEqual(repo.get_document("tenant", "case", original.id).current_version_id, old_id)
                self.assertEqual(len(repo.list_versions("tenant", "case", original.id)), 1)
                self.assertEqual(repo.get_extracted_text("tenant", "case", original.id, old_id).text, extract.text)
                renewed = service.reacquire_existing_version("tenant", "case", original.id, b"original document", context)
                self.assertNotEqual(renewed.version_id, old_id)
                self.assertEqual(repo.get_document("tenant", "case", original.id).current_version_id, renewed.version_id)
                self.assertEqual(len(repo.list_versions("tenant", "case", original.id)), 2)
                self.assertEqual(len(repo.list_documents("tenant", "case")), 1)
                self.assertIsNone(repo.get_document("other-tenant", "case", original.id))
            repo.close()

if __name__ == "__main__":
    unittest.main()
