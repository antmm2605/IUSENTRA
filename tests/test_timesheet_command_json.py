"""Guardrail dei comandi Timesheet dopo la prova reale della conferma React."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from pct.storage import StudioDB
from pct.timesheet import GestioneTimesheet, StatoTimesheet
from web.bootstrap.timesheet_routes import register_timesheet_routes


class TimesheetCommandJsonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.db = StudioDB(str(self.base / "studio.db"))
        self.repo = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db)
        self.audit_events = []
        self.app = Flask(__name__)
        self.app.secret_key = "controlled-timesheet-test"
        self.app.testing = True

        @self.app.before_request
        def user():
            g.utente_corrente = SimpleNamespace(id="operatore", username="operatore")

        register_timesheet_routes(
            self.app,
            get_timesheet=lambda: self.repo,
            get_clienti=lambda: None,
            get_fascicoli=lambda: None,
            get_fatturazione=lambda: None,
            audit=lambda *args, **kwargs: self.audit_events.append((args, kwargs)),
        )
        self.client = self.app.test_client()
        self.headers = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}

    def tearDown(self):
        self.db.chiudi()
        self.temp.cleanup()

    def test_json_creation_is_confirmed_once_and_persists_in_sql(self):
        response = self.client.post("/timesheet/nuovo", headers=self.headers, data={
            "descrizione": "Studio interfaccia — attività interna", "minuti": "1",
            "data_attivita": "2026-10-05", "fatturabile": "0", "valore_unitario": "0",
        })
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertNotIn("Location", response.headers)
        loaded = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db)
        self.assertEqual(len(loaded.tutte()), 1)
        entry = loaded.get(payload["id"])
        self.assertFalse(entry.fatturabile)
        self.assertEqual(entry.descrizione, "Studio interfaccia — attività interna")
        self.assertEqual(self.audit_events[0][0][0], "timesheet.crea")
        status = self.client.post(f"/timesheet/{entry.id}/stato", headers=self.headers, data={"stato": "ANNULLATO"})
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["stato"], "ANNULLATO")
        loaded = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db)
        self.assertEqual(loaded.get(entry.id).stato, StatoTimesheet.ANNULLATO)
        self.assertEqual(loaded.statistiche()["totale_minuti"], 0)
        self.assertEqual(self.audit_events[-1][0][0], "timesheet.stato")

    def test_invalid_input_and_unknown_entry_do_not_report_success(self):
        response = self.client.post("/timesheet/nuovo", headers=self.headers, data={"descrizione": "Prova", "minuti": "0"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(self.repo.tutte(), [])
        missing = self.client.post("/timesheet/missing/stato", headers=self.headers, data={"stato": "ANNULLATO"})
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.get_json()["ok"])
        self.assertEqual(self.audit_events, [])

    def test_normal_form_keeps_its_existing_redirect(self):
        response = self.client.post("/timesheet/nuovo", data={"descrizione": "Attività interna", "minuti": "1", "fatturabile": "0"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/timesheet", response.headers["Location"])
        self.assertEqual(len(self.repo.tutte()), 1)


if __name__ == "__main__":
    unittest.main()