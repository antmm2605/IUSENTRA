"""Regressioni SQL del pannello già provato materialmente in produzione."""
import os
import sqlite3
import unittest
import uuid
from contextlib import contextmanager

from pct.notifications.models import NotificationRecord
from pct.notifications.repository import (
    NotificationRepository,
    POSTGRES_SCHEMA_NOTIFICATIONS,
    SQLITE_SCHEMA_NOTIFICATIONS,
)
from tests.test_condivisioni_sql_repository import SQLFactory


class NotificationPagesSQLite(unittest.TestCase):
    backend = 'sqlite'

    @classmethod
    def setUpClass(cls):
        cls.factory = SQLFactory(cls.backend)
        cls.db = cls.factory.new()
        if cls.backend == 'sqlite':
            cls.db.conn.row_factory = sqlite3.Row
        schema = POSTGRES_SCHEMA_NOTIFICATIONS if cls.backend == 'postgresql' else SQLITE_SCHEMA_NOTIFICATIONS
        try:
            for statement in schema.read_text(encoding='utf-8').split(';'):
                if statement.strip():
                    cls.db.conn.execute(statement)
            cls.factory.commit(cls.db)
        except Exception:
            cls.factory.close()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.factory.close()

    def setUp(self):
        self.tenant = uuid.uuid4().hex
        self.user = uuid.uuid4().hex
        self.repo = object.__new__(NotificationRepository)

        @contextmanager
        def controlled_connection():
            yield self.db.conn
            self.factory.commit(self.db)

        self.repo._connect = controlled_connection
        self.records = []
        for index in range(75):
            record = NotificationRecord(tenant_id=self.tenant, user_id=self.user,
                title=f'Attività {index:03d}', body='Fascicolo RG 867/2026',
                dedupe_key=f'controlled:{index}', created_at='2026-10-01T12:00:00Z')
            saved, _ = self.repo.upsert_notification(record)
            self.records.append(saved)

    def page(self, **options):
        return self.repo.notification_page(self.tenant, self.user, **options)

    def test_count_is_not_capped_to_fifty(self):
        result = self.page()
        self.assertEqual((result['totalCount'], result['unreadCount'], result['pageCount']), (75, 75, 3))
        self.assertEqual(len(result['records']), 30)

    def test_stable_paging_includes_every_record_once(self):
        ids = [row.id for page in range(1, 4) for row in self.page(page=page)['records']]
        self.assertEqual(set(ids), {row.id for row in self.records})
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.page(page=999)['page'], 3)

    def test_read_filter_tracks_persistent_mutation(self):
        self.repo.mark_read(self.tenant, self.user, self.records[0].id)
        read = self.page(state='read')
        self.assertEqual((read['filteredCount'], read['unreadCount']), (1, 74))
        self.assertEqual(self.page(state='unread')['filteredCount'], 74)
        self.repo.mark_all_read(self.tenant, self.user)
        self.assertEqual(self.page(state='unread')['filteredCount'], 0)

    def test_user_and_tenant_isolation(self):
        self.assertEqual(self.repo.notification_page(self.tenant, 'other')['totalCount'], 0)
        self.assertEqual(self.repo.notification_page('other', self.user)['totalCount'], 0)
        self.assertFalse(self.repo.mark_read('other', self.user, self.records[0].id))
        self.assertEqual(self.page()['unreadCount'], 75)

    def test_search_is_literal_and_bound(self):
        self.assertEqual(self.page(query='rg 867/2026')['filteredCount'], 75)
        self.assertEqual(self.page(query='%')['filteredCount'], 0)
        self.assertEqual(self.page(query="' OR 1=1 --")['filteredCount'], 0)
        with self.assertRaises(ValueError):
            self.page(state='invalid')

    def test_expired_projection_is_excluded_without_marking_read(self):
        record = self.records[0]
        self.repo.expire_notifications_by_source_ids(self.tenant, self.user, source_type='missing', source_ids={'missing'})
        with self.repo._connect() as conn:
            conn.execute('UPDATE notifications SET expires_at=? WHERE tenant_id=? AND id=?', ('2020-01-01T00:00:00Z', self.tenant, record.id))
        self.assertEqual(self.page()['totalCount'], 74)
        with self.repo._connect() as conn:
            row = conn.execute('SELECT read_at FROM notifications WHERE tenant_id=? AND id=?', (self.tenant, record.id)).fetchone()
        self.assertEqual(dict(row)['read_at'], '')


@unittest.skipUnless(os.environ.get('AUDIT_POSTGRES_PASSWORD'), 'PostgreSQL controllato non configurato')
class NotificationPagesPostgres(NotificationPagesSQLite):
    backend = 'postgresql'


if __name__ == '__main__':
    unittest.main()
