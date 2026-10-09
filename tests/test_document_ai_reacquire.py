import io
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pct.document_intelligence.extraction import ExtractionResult
from pct.document_intelligence.repository import DocumentAIRepository
from pct.document_intelligence.service import DocumentAIService
from pct.document_intelligence.models import DocumentAIPageText
from legal_ocr.motore.identita import RECUPERO_IDENTITA_VERSIONE

class ReacquireTests(unittest.TestCase):
    def test_identity_recovery_preserves_archived_text_and_does_not_retry_same_hash(self):
        for positive in (False, True):
            with self.subTest(positive=positive), tempfile.TemporaryDirectory() as folder, closing(
                DocumentAIRepository.from_sqlite_db(Path(folder)/"studio.db", storage_root=Path(folder)/"blobs")
            ) as repo:
                service = DocumentAIService(repo)
                context = {"skip_permission_check": True, "user_id": "controlled-test"}
                upload = io.BytesIO(b"original document")
                upload.filename, upload.content_type = "source.txt", "text/plain"
                original_text = "Testo precedente da preservare integralmente"
                extraction = ExtractionResult(ok=True, text=original_text,
                    pages=[DocumentAIPageText(page_number=1, text=original_text)], extraction_engine="test")
                with patch("pct.document_intelligence.service.extract_text_from_document", return_value=extraction):
                    record = service.upload_document_for_fascicolo("tenant", "case", upload, context).document
                fresh = ExtractionResult(ok=positive, text="Testo nuovo peggiore", pages=[], extraction_engine="test",
                    identity_recoveries=[DocumentAIPageText(page_number=1, text="MRZ verificata")] if positive else [])
                with patch("pct.document_intelligence.service.extract_text_from_document", return_value=fresh) as read:
                    renewed = service.reacquire_existing_version("tenant", "case", record.id, b"original document", context, identity_recovery=True)
                    self.assertTrue(renewed.text.startswith(original_text))
                    self.assertNotIn("Testo nuovo peggiore", renewed.text)
                    self.assertEqual("MRZ verificata" in renewed.text, positive)
                    self.assertEqual("MRZ verificata" in renewed.pages[0].text, positive)
                    self.assertTrue(any(f"Recupero identità {RECUPERO_IDENTITA_VERSIONE}:" in warning for warning in renewed.warnings))
                    repeated = service.reacquire_existing_version("tenant", "case", record.id, b"original document", context, identity_recovery=True)
                    self.assertEqual(repeated.version_id, renewed.version_id)
                    self.assertEqual(read.call_count, 1)
                    self.assertEqual(len(repo.list_versions("tenant", "case", record.id)), 2)

    def test_sql_version_switch_is_atomic(self):
        with tempfile.TemporaryDirectory() as folder, closing(
            DocumentAIRepository.from_sqlite_db(Path(folder)/"studio.db", storage_root=Path(folder)/"blobs")
        ) as repo:
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

if __name__ == "__main__":
    unittest.main()
