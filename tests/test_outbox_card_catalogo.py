"""Guardrail SQL della consultazione, senza eventi operativi o dispatcher."""
import sys
import unittest

from pct.data_consistency import list_outbox_metadata
from tests.test_condivisioni_sql_repository import SQLFactory


class EventCatalogChecks(unittest.TestCase):
    backend = "sqlite"

    def setUp(self):
        self.factory = SQLFactory(self.backend)
        self.addCleanup(self.factory.close)
        self.db = self.factory.new()
        self.db.conn.execute("CREATE TABLE transactional_outbox (id TEXT PRIMARY KEY, aggregate_type TEXT, aggregate_id TEXT, event_type TEXT, status TEXT, attempts INTEGER, created_at TEXT, processed_at TEXT, payload_json TEXT, actor_id TEXT, last_error TEXT)")
        for i in range(121):
            self.db.conn.execute("INSERT INTO transactional_outbox VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                 (f"event-{i:03d}", "fascicolo", f"case-{i}", "created", "FAILED" if i < 7 else "PENDING", i % 3, "2026-10-05T12:00:00Z", None, "private payload", "private actor", "private error"))
        self.db.conn.execute("INSERT INTO transactional_outbox VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                             ("literal", "literal", "ref_%", "literal", "PROCESSED", 1, "2026-10-05T13:00:00Z", "2026-10-05T14:00:00Z", "private", "actor", "error"))
        self.factory.commit(self.db)

    def test_all_pages_exact_catalogue_without_overlap(self):
        pages = [list_outbox_metadata(self.db, page=page) for page in (1, 2, 3)]
        self.assertEqual([len(page["records"]) for page in pages], [50, 50, 22])
        self.assertTrue(all(page["total"] == 122 for page in pages))
        self.assertEqual(len({record["id"] for page in pages for record in page["records"]}), 122)
        self.assertEqual(list_outbox_metadata(self.db, page=1000)["page"], 3)

    def test_status_query_and_wildcard_literal(self):
        self.assertEqual(list_outbox_metadata(self.db, status="FAILED")["total"], 7)
        self.assertEqual(list_outbox_metadata(self.db, status="PENDING", query="CASE-")["total"], 114)
        self.assertEqual(list_outbox_metadata(self.db, query="_%")["total"], 1)
        self.assertEqual(list_outbox_metadata(self.db, query="' OR 1=1 --")["total"], 0)
        with self.assertRaises(ValueError):
            list_outbox_metadata(self.db, status="UNRECOGNIZED")

    def test_metadata_only_and_read_only(self):
        result = list_outbox_metadata(self.db)
        for row in result["records"]:
            self.assertTrue({"payload_json", "actor_id", "last_error"}.isdisjoint(row))
        count = self.db.conn.execute("SELECT COUNT(*) AS n FROM transactional_outbox").fetchone()
        self.assertEqual(count['n'] if hasattr(count,'keys') else count[0], 122)
        self.assertEqual(list_outbox_metadata(self.db, status="FAILED")["total"], 7)


if __name__ == "__main__":
    EventCatalogChecks.backend = "postgresql" if "--postgresql" in sys.argv else "sqlite"
    sys.argv = [arg for arg in sys.argv if arg != "--postgresql"]
    unittest.main(verbosity=2)
