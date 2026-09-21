import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pct.scheduler_health import _RegistroSoloLettura, format_heartbeat_lines, presidio_heartbeat

class PersistedScheduleHealthTests(unittest.TestCase):
    def test_pause_preserves_failure_and_reenable_restores_alarm(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'scheduler.sqlite'
            now = datetime.now(timezone.utc)
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('CREATE TABLE scheduled_jobs(job_id TEXT PRIMARY KEY, enabled INTEGER)')
                conn.execute('CREATE TABLE scheduled_job_runs(id INTEGER PRIMARY KEY, job_id TEXT, status TEXT, finished_at TEXT, started_at TEXT, created_at TEXT, message TEXT, error_message TEXT)')
                conn.execute("INSERT INTO scheduled_jobs VALUES ('case-reader', 0)")
                conn.execute("INSERT INTO scheduled_job_runs VALUES (1,'case-reader','failed',?,'','','','original failure')", ((now-timedelta(hours=2)).isoformat(),))
                conn.commit()
            repo = _RegistroSoloLettura(path)
            paused = presidio_heartbeat(repo, now=now, jobs=(('case-reader','Lettura',45),))
            self.assertTrue(paused['ok'])
            self.assertEqual(paused['presidi'][0]['status'],'paused')
            self.assertEqual(paused['presidi'][0]['error'],'original failure')
            self.assertIn('sospeso', format_heartbeat_lines(paused)[0])
            with closing(sqlite3.connect(path)) as conn:
                conn.execute('UPDATE scheduled_jobs SET enabled=1')
                conn.commit()
            resumed = presidio_heartbeat(repo, now=now, jobs=(('case-reader','Lettura',45),))
            self.assertFalse(resumed['ok'])
            self.assertEqual(resumed['hard_failures'],1)

if __name__ == '__main__':
    unittest.main()
