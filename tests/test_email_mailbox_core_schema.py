"""Il catalogo della posta fa parte dei due schemi core nativi."""
import unittest
import os
from pathlib import Path

from tests.test_condivisioni_sql_repository import SQLFactory
from pct.database import SCHEMA_SQL
from pct.storage_postgres import CORE_POSTGRES_SCHEMA_SQL
from pct.email_mailbox_repository import DDL, EmailMailboxRepository, MailboxNotInitialized


class NativeSchemaChecks(unittest.TestCase):
    backend = None

    @classmethod
    def setUpClass(cls):
        if cls.backend is None:
            raise unittest.SkipTest('Classe base: usare i due backend.')
        cls.factory = SQLFactory(cls.backend)
        try:
            cls.db = cls.factory.new()
            schema = SCHEMA_SQL if cls.backend == 'sqlite' else CORE_POSTGRES_SCHEMA_SQL
            if cls.backend == 'sqlite':
                cls.db.conn.executescript(schema)
            else:
                cls.db.conn.execute(schema)
            cls.factory.commit(cls.db)
        except Exception:
            cls.factory.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.factory.close()

    def test_primary_catalog_exists_in_native_core_with_same_columns(self):
        expected = ['tenant_key', 'mailbox_kind', 'message_key', 'folder', 'read_state',
                    'message_date', 'payload_json', 'updated_at']
        if self.backend == 'sqlite':
            actual = [row[1] for row in self.db.conn.execute('PRAGMA table_info(email_mailbox_records)').fetchall()]
        else:
            actual = [row[0] for row in self.db.conn.execute(
                'SELECT column_name FROM information_schema.columns '
                'WHERE table_schema=current_schema() AND table_name=? ORDER BY ordinal_position',
                ('email_mailbox_records',),
            ).fetchall()]
        self.assertEqual(actual, expected)
        repo = EmailMailboxRepository(self.db, 'controlled-schema', 'pec')
        with self.assertRaises(MailboxNotInitialized):
            repo.load()
        repo.initialize({}, source_of_truth=self.backend)
        self.assertEqual(repo.load(), {})

    def test_versioned_migration_matches_portable_runtime_ddl_and_is_idempotent(self):
        root = Path(os.environ.get('MAILBOX_SCHEMA_ROOT', str(Path(__file__).resolve().parents[1])))
        filename = '20261006_email_mailbox.sql' if self.backend == 'sqlite' else '20261006_email_mailbox_postgres.sql'
        content = (root / 'pct/sql' / filename).read_text(encoding='utf-8')
        statements = [statement.strip() for statement in '\n'.join(
            line for line in content.splitlines() if not line.lstrip().startswith('--')).split(';') if statement.strip()]
        self.assertEqual([' '.join(statement.split()) for statement in statements],
                         [' '.join(statement.split()) for statement in DDL])
        for _ in range(2):
            for statement in statements:
                self.db.conn.execute(statement)
            self.factory.commit(self.db)


class SQLiteNativeSchema(NativeSchemaChecks):
    backend = 'sqlite'


@unittest.skipUnless(os.environ.get('AUDIT_POSTGRES_PASSWORD'), 'PostgreSQL controllato non configurato: eseguire nel profilo di test SQL.')
class PostgreSQLNativeSchema(NativeSchemaChecks):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
