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
            g.utente_corrente = SimpleNamespace(id=getattr(self, "actor_id", "operatore"), username="operatore",
                ha_permesso=lambda permission: getattr(self, "can_write", True))

        register_timesheet_routes(
            self.app,
            get_timesheet=lambda: self.repo,
            get_clienti=lambda: None,
            get_fascicoli=lambda: SimpleNamespace(get=lambda key: None),
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
        status = self.client.post(f"/timesheet/{entry.id}/stato", headers=self.headers, data={"stato": "ANNULLATO", "revision": entry.revisione})
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["stato"], "ANNULLATO")
        loaded = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db)
        self.assertEqual(loaded.get(entry.id).stato, StatoTimesheet.ANNULLATO)
        self.assertEqual(loaded.statistiche()["totale_minuti"], 0)
        self.assertEqual(self.audit_events[-1][0][0], "timesheet.stato")

    def seed_proposal(self):
        from pct.tracking_passivo_sql import TrackingPassivoSQL
        self.db.conn.execute("INSERT INTO fascicoli (id) VALUES (?)", ("case",))
        self.db.conn.commit()
        tracking = TrackingPassivoSQL(self.db)
        tracking.insert([dict(id="proposal", chiave="operatore|case|2026-10-17T10:00", stato="BOZZA",
            utente_id="operatore", fascicolo_id="case", inizio="2026-10-17T10:00:00", minuti=12,
            descrizione="Studio della pratica", username="operatore")])
        return tracking

    def test_proposal_confirmation_repeated_returns_same_entry_and_one_audit(self):
        self.seed_proposal()
        first = self.client.post('/timesheet/proposte/proposal/conferma', headers=self.headers, json={})
        again = self.client.post('/timesheet/proposte/proposal/conferma', headers=self.headers, json={})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(again.status_code, 200)
        self.assertEqual(first.json['proposta']['voce_timesheet_id'], again.json['proposta']['voce_timesheet_id'])
        self.assertTrue(again.json['proposta']['gia_presente'])
        self.assertEqual(len(self.repo.tutte()), 1)
        self.assertEqual(len(self.audit_events), 1)
        discard = self.client.post('/timesheet/proposte/proposal/scarta', headers=self.headers, json={})
        self.assertEqual(discard.status_code, 409)
        self.assertEqual(len(self.audit_events), 1)

    def test_proposal_requires_permission_and_preserves_activity_owner(self):
        tracking = self.seed_proposal()
        self.can_write = False
        forbidden = self.client.post('/timesheet/proposte/proposal/conferma', headers=self.headers, json={})
        self.assertEqual(forbidden.status_code, 403)
        self.can_write = True
        self.actor_id = 'altro'
        foreign = self.client.post('/timesheet/proposte/proposal/conferma', headers=self.headers, json={})
        self.assertEqual(foreign.status_code, 200)
        self.assertEqual(tracking.get('proposal')['stato'], 'CONFERMATA')
        self.assertEqual(tracking.get('proposal')['definito_da'], 'altro')
        entry = self.repo.get(foreign.get_json()['proposta']['voce_timesheet_id'])
        self.assertEqual(entry.id_utente, 'operatore')
        self.assertEqual(len(self.audit_events), 1)

    def test_proposal_lookup_failure_returns_json_without_success(self):
        from unittest.mock import patch
        from pct.time_tracking_passivo import GestioneTrackingPassivo
        with patch.object(GestioneTrackingPassivo, 'get', side_effect=RuntimeError('Repository non disponibile')):
            for action in ('conferma', 'scarta'):
                result = self.client.post(f'/timesheet/proposte/proposal/{action}', headers=self.headers, json={})
                self.assertEqual(result.status_code, 500)
                self.assertFalse(result.get_json()['ok'])
        self.assertEqual(self.repo.tutte(), [])
        self.assertEqual(self.audit_events, [])

    def test_negative_minutes_are_rejected_without_confirming(self):
        tracking = self.seed_proposal()
        result = self.client.post('/timesheet/proposte/proposal/conferma', headers=self.headers, json={'minuti': '-1'})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(tracking.get('proposal')['stato'], 'BOZZA')
        self.assertEqual(self.repo.tutte(), [])

    def test_invalid_input_and_unknown_entry_do_not_report_success(self):
        response = self.client.post("/timesheet/nuovo", headers=self.headers, data={"descrizione": "Prova", "minuti": "0"})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(self.repo.tutte(), [])
        missing = self.client.post("/timesheet/missing/stato", headers=self.headers, data={"stato": "ANNULLATO"})
        self.assertEqual(missing.status_code, 404)
        self.assertFalse(missing.get_json()["ok"])
        self.assertEqual(self.audit_events, [])

    def test_conflict_reports_409_without_success_or_audit(self):
        entry = self.repo.crea(descrizione="Voce condivisa", minuti=1)
        newer = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db)
        newer.aggiorna(entry.id, note="Confermata da altro processo")
        response = self.client.post(f"/timesheet/{entry.id}/stato", headers=self.headers, data={"stato": "ANNULLATO", "revision": entry.revisione})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.get_json()["ok"])
        self.assertIn("altro processo", response.get_json()["message"])
        self.assertEqual(self.audit_events, [])
        persisted = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db).get(entry.id)
        self.assertEqual(persisted.note, "Confermata da altro processo")
        self.assertEqual(persisted.stato, StatoTimesheet.APERTO)

    def test_old_ui_revision_is_rejected_even_with_fresh_repository(self):
        entry = self.repo.crea(descrizione="Revisioni concorrenti", minuti=1)
        old_revision = entry.revisione
        self.repo.aggiorna(entry.id, note="Modifica successiva già confermata")
        self.repo = GestioneTimesheet(str(self.base / "timesheet.json"), studio_db=self.db)
        response = self.client.post(f"/timesheet/{entry.id}/stato", headers=self.headers,
                                    data={"stato": "ANNULLATO", "revision": old_revision})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(self.repo.get(entry.id).stato, StatoTimesheet.APERTO)
        self.assertEqual(self.audit_events, [])

    def test_missing_revision_does_not_confirm_a_state(self):
        entry = self.repo.crea(descrizione="Scheda precedente al rilascio", minuti=1)
        response = self.client.post(f"/timesheet/{entry.id}/stato", headers=self.headers,
                                    data={"stato": "ANNULLATO"})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.get_json()["ok"])
        self.assertEqual(self.repo.get(entry.id).stato, StatoTimesheet.APERTO)
        self.assertEqual(self.audit_events, [])

    def test_normal_form_keeps_its_existing_redirect(self):
        response = self.client.post("/timesheet/nuovo", data={"descrizione": "Attività interna", "minuti": "1", "fatturabile": "0"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/timesheet", response.headers["Location"])
        self.assertEqual(len(self.repo.tutte()), 1)


if __name__ == "__main__":
    unittest.main()
