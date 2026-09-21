import tempfile
import gc
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock
from pct.local_ai import LocalAIService
from web.services.rag_archivio_runtime import indicizza_testi_archivio

class ArchiveRagTests(unittest.TestCase):
    def test_boundary_delimiter_never_exceeds_limit_or_loses_text(self):
        from pct.local_ai import _bounded_text_parts
        from lex.retrieval.chunking import bounded_text_chunks
        for split in (_bounded_text_parts, bounded_text_chunks):
            for separator in (". ", "; ", "\n\n", " "):
                text = "a" * 3199 + separator + "b" * 3200
                chunks = split(text, max_chars=3200)
                self.assertEqual("".join(chunks), text)
                self.assertLessEqual(max(map(len, chunks)), 3200)

    def test_changed_case_only_and_real_page_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            rag = LocalAIService(db_path=str(root/"rag.db"), policy_path=str(root/"policy.json"), config_path=str(root/"studio.json"), app_root=str(Path(__file__).resolve().parents[1]), models_path=str(root/"models"))
            repo, registry = Mock(), Mock()
            repo.backend_kind = "sqlite"
            repo.list_documents.return_value = [NS(id="sql-id", sha256="content-hash", status="ready", current_version_id="v2", updated_at="2026-09-21")]
            pages = [NS(page_number=2, text="Il ricorso contiene la domanda del ricorrente."), NS(page_number=4, text="Il decreto assegna il termine per le note scritte.")]
            repo.get_extracted_text.return_value = NS(text="\n\n".join(p.text for p in pages), pages=pages, extraction_engine="pdf-native")
            obj = NS(oggetto_id="original-id", sha256="content-hash", presente=True)
            registry.da_leggere.return_value = [obj, NS(oggetto_id="other-id", sha256="other", presente=True)]
            case = NS(id="target-case", documenti=[NS(id="original-id", nome="Fonte.pdf")])
            report = indicizza_testi_archivio(case, repo, rag, registry, "tenant")
            self.assertEqual(report["indexed"], 1)
            registry.da_leggere.assert_called_once_with("tenant", "target-case", "rag_locale", tipi=("documento",))
            with rag._connect() as conn:
                rows = conn.execute("SELECT practice_id,page_from,page_to,text FROM rag_chunks ORDER BY ordinal").fetchall()
                self.assertEqual({r[0] for r in rows}, {"target-case"})
                self.assertEqual({r[1] for r in rows}, {2,4})
                self.assertTrue(all(r[1] == r[2] for r in rows))
            conn.close()
            registry.da_leggere.return_value = []
            repo.reset_mock()
            self.assertEqual(indicizza_testi_archivio(case, repo, rag, registry, "tenant")["indexed"], 0)
            repo.list_documents.assert_not_called()
            # SQLite cursors can retain connection cycles until collection on Windows.
            gc.collect()

if __name__ == "__main__":
    unittest.main()
