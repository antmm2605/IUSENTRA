from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g

from pct.pec_control_tower import PecControlTowerRepository, build_synthetic_pec_eml
from web.blueprints.pec_control_tower_api import pec_control_tower_api


class _User:
    id = "user-test"
    username = "Avvocato Test"
    tenant_slug = "tenant-test"

    def ha_permesso(self, permission: str) -> bool:
        return permission in {"ai.usa", "messaggi.leggi", "fascicoli.leggi"}


def _fascicoli_rows():
    return [
        SimpleNamespace(
            id="FASC-2026-001",
            numero="RG 1234/2026",
            titolo="Rossi c. Comune",
            oggetto="Comunicazione cancelleria RG 1234/2026",
            procedimento="RG 1234/2026",
            nome_cliente="Mario Rossi",
            controparte="Comune",
        )
    ]


def _sample_court_pec() -> bytes:
    return build_synthetic_pec_eml(
        subject="Comunicazione di cancelleria RG 1234/2026 - deposito provvedimento",
        body="Deposito provvedimento nel fascicolo RG 1234/2026. Verificare termini e documenti.",
        sender="cancelleria@giustiziacert.it",
        dt=datetime.now(timezone.utc),
        attachments={"provvedimento.pdf.txt": "Provvedimento di test RG 1234/2026."},
    )


def test_pec_control_tower_repository_tracks_event_deadline_task_and_audit(tmp_path):
    repo = PecControlTowerRepository(
        tmp_path / "pec_control_tower.sqlite",
        tenant_id="tenant-test",
        fascicoli_rows=_fascicoli_rows(),
    )

    result = repo.ingest_eml(_sample_court_pec(), account_email="studio@example.pec.it", actor="pytest")
    communication = result["data"]

    assert communication["legal_category"] == "PROVVEDIMENTO_GIUDIZIARIO"
    assert communication["fascicolo_id"] == "FASC-2026-001"
    assert communication["events"]
    assert communication["deadlines"]
    assert communication["tasks"]
    assert communication["events"][0]["expected_documents"]
    assert communication["events"][0]["legal_articles"]
    assert repo.verify_audit_chain()["ok"] is True

    tables = {
        row[0]
        for row in repo._connect().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {
        "legal_communications",
        "pec_receipt_events",
        "legal_deadlines",
        "agenda_events",
        "notification_jobs",
        "notification_recipients",
        "registry_lookups",
        "legal_rule_versions",
        "audit_events",
    }.issubset(tables)


def test_pec_control_tower_generation_script_answers_lex_matrix(tmp_path):
    script = Path("scripts/test_pec_control_tower.py")
    completed = subprocess.run(
        [sys.executable, str(script), "--runtime-root", str(tmp_path / "runtime")],
        cwd=Path.cwd(),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["audit"]["ok"] is True
    assert len(payload["answers"]) == 10
    assert any("Prova: completa" in item["answer"] for item in payload["answers"])
    assert any("Scadenza" in item["answer"] and "da confermare" in item["answer"] for item in payload["answers"])


def test_pec_control_tower_api_ingest_list_and_confirm_deadline(tmp_path, monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True)

    paths = {
        "EMAIL_CASELLA_DB": tmp_path / "email" / "casella.json",
        "FASCICOLI_DB": tmp_path / "fascicoli" / "fascicoli.json",
        "FASCICOLI_DOCS": tmp_path / "fascicoli" / "documenti",
        "SCADENZIARIO_DB": tmp_path / "scadenziario" / "scadenze.json",
        "AGENDA_DB": tmp_path / "agenda" / "appuntamenti.json",
    }
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            path.mkdir(parents=True, exist_ok=True)

    def fake_tenant_data_path(key, default="", *aliases, require_tenant=True):
        return str(paths[key])

    monkeypatch.setattr("web.blueprints.pec_control_tower_api.tenant_data_path", fake_tenant_data_path)

    @app.before_request
    def _auth():
        g.utente_corrente = _User()
        g.tenant_slug = "tenant-test"
        g.data_paths = {"PEC_CONTROL_TOWER_DB": str(tmp_path / "email" / "pec_control_tower.sqlite")}

    app.register_blueprint(pec_control_tower_api, url_prefix="/api")

    with app.test_client() as client:
        ingest = client.post(
            "/api/pec/ingest",
            data=_sample_court_pec(),
            content_type="message/rfc822",
            headers={"X-IUSENTRA-PEC-ACCOUNT": "studio@example.pec.it"},
        )
        assert ingest.status_code == 201
        communication = ingest.get_json()["data"]
        assert communication["legal_category"] == "PROVVEDIMENTO_GIUDIZIARIO"

        listing = client.get("/api/communications")
        assert listing.status_code == 200
        assert listing.get_json()["count"] == 1

        deadlines = client.get("/api/deadlines")
        assert deadlines.status_code == 200
        deadline_id = deadlines.get_json()["data"][0]["id"]

        confirmed = client.post(
            f"/api/deadlines/{deadline_id}/confirm",
            json={"confirmation_rule": "Verifica avvocato su fascicolo e comunicazione PEC."},
        )
        assert confirmed.status_code == 200
        assert confirmed.get_json()["data"]["status"] == "confirmed"

        audit = client.get("/api/audit/")
        assert audit.status_code == 200
        assert audit.get_json()["chain"]["ok"] is True
