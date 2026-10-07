"""Guardrail SQL: le card non filtrano le sole anteprime del sito."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pct.studio_site_repository import StudioSiteRepository
from web.services import react_sito_studio_bridge as bridge


class SitoCardCataloghiTests(unittest.TestCase):
    def test_cataloghi_sql_completi_e_isolamento_sito(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = StudioSiteRepository(str(Path(directory) / 'controlled.db'))
            with repo._connect() as conn:
                conn.execute("INSERT INTO site_studio (id, tenant_slug, site_name, public_slug) VALUES (1,'controllato','Controllato','controllato')")
                conn.execute("INSERT INTO site_studio (id, tenant_slug, site_name, public_slug) VALUES (2,'altro','Altro','altro')")
                for site_id, count in ((1, 1001), (2, 1)):
                    conn.executemany("INSERT INTO site_contact_submission (site_id,full_name,email,message) VALUES (?,?,?,?)", [(site_id, f'Contatto {i}', f'{i}@example.invalid', 'Controllato') for i in range(count)])
                    conn.executemany("INSERT INTO site_booking_request (site_id,customer_name,customer_email,requested_date,requested_time) VALUES (?,?,?,?,?)", [(site_id, f'Richiesta {i}', f'{i}@example.invalid', '2026-10-06', '09:30') for i in range(count)])
                    conn.executemany("INSERT INTO site_article (site_id,title,slug) VALUES (?,?,?)", [(site_id, f'Articolo {i}', f'articolo-{i}') for i in range(13 if site_id == 1 else 1)])
                conn.commit()
            preview = {'site': {'id': 1}, 'articles': repo.list_articles(1, limit=6), 'contact_submissions': repo.list_contact_submissions(1, limit=10), 'booking_requests': repo.list_booking_requests(1, limit=10)}
            with patch.object(bridge, 'build_studio_site_dashboard_payload', return_value=preview), patch.object(bridge, 'studio_site_repository', return_value=repo):
                result = bridge._base_dashboard()
            self.assertEqual(len(result['articles']), 13)
            self.assertEqual(len(result['contact_submissions']), 1001)
            self.assertEqual(len(result['booking_requests']), 1001)
            for key in ('articles', 'contact_submissions', 'booking_requests'):
                self.assertEqual({row['site_id'] for row in result[key]}, {1})

    def test_clienti_sql_oltre_ottanta(self):
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE clienti_controllati (id TEXT, nome TEXT)')
            conn.executemany('INSERT INTO clienti_controllati VALUES (?,?)', [(str(i), f'Cliente {i}') for i in range(97)])
            manager = SimpleNamespace(tutti=lambda: [SimpleNamespace(id=row[0], nome_completo=row[1]) for row in conn.execute('SELECT id,nome FROM clienti_controllati ORDER BY CAST(id AS INTEGER)')])
            user = SimpleNamespace(ha_permesso=lambda permission: permission == 'clienti.leggi')
            rows = bridge._safe_clients(lambda: manager, user)
            self.assertEqual(len(rows), 97)
            self.assertEqual(rows[-1]['id'], '96')

    def test_clienti_non_esposti_senza_permesso(self):
        def forbidden_loader():
            self.fail('Il repository non deve essere letto senza permesso')
        self.assertEqual(bridge._safe_clients(forbidden_loader, SimpleNamespace(ha_permesso=lambda permission: False)), [])


if __name__ == '__main__':
    unittest.main()
