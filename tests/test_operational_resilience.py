from __future__ import annotations

import os
from pathlib import Path

from pct.backup import GestioneBackup
from pct.operational_resilience import (
    _write_json,
    _run_pytest_phase,
    run_operational_backup_plan,
    run_operational_crash_test,
)
from pct.operational_resilience_repository import OperationalResilienceRepository
from tests.test_operational_surfaces import _cfg_web, _seed_runtime, _write_studio_config
from web.app import create_app
from web.services.operational_resilience_surface import build_operational_crash_surface


def test_run_operational_crash_test_crea_report_ticket_e_persistenza(tmp_path: Path, monkeypatch):
    repository = OperationalResilienceRepository(sqlite_path=str(tmp_path / "operational.db"))

    def _fake_phase(selectors, **kwargs):
        selector_text = " ".join(selectors)
        if "dirty_data" in selector_text:
            return {
                "status": "failed",
                "return_code": 1,
                "duration_seconds": 0.21,
                "output_excerpt": "Il test dirty data ha bloccato una regressione.",
            }
        return {
            "status": "passed",
            "return_code": 0,
            "duration_seconds": 0.12,
            "output_excerpt": "Fase superata.",
        }

    monkeypatch.setattr("pct.operational_resilience._run_pytest_phase", _fake_phase)

    report = run_operational_crash_test(
        tenant_slug="studio-test",
        report_dir=str(tmp_path / "reports"),
        repair_dir=str(tmp_path / "repair"),
        repository=repository,
        health_snapshot_factory=lambda: {
            "db": "ok",
            "scheduler": "ok",
            "ocr": "ok",
            "ai": "ok",
            "actions_required": [],
        },
        auto_repair=False,
        max_attempts=1,
        cwd=str(tmp_path),
    )

    assert report["overall_ok"] is False
    assert Path(report["report_path"]).exists()
    assert report["repair_ticket_paths"]
    assert any(row["phase_id"] == "dirty_data" and row["status"] == "failed" for row in report["phases"])

    latest_run = repository.latest_crash_run(tenant_slug="studio-test")
    tickets = repository.list_repair_tickets(tenant_slug="studio-test")

    assert latest_run is not None
    assert latest_run["report_path"] == report["report_path"]
    assert tickets
    assert tickets[0]["action_code"] == "DIRTY_DATA_NOT_BLOCKED"


def test_run_operational_backup_plan_salva_report_e_copie(tmp_path: Path):
    source_dir = tmp_path / "dati"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "clienti.json").write_text('{"clienti": []}', encoding="utf-8")
    (source_dir / "fascicoli.json").write_text('{"fascicoli": []}', encoding="utf-8")

    backup_manager = GestioneBackup(
        directory_backup=str(tmp_path / "backup"),
        percorsi_dati={
            "clienti": str(source_dir / "clienti.json"),
            "fascicoli": str(source_dir / "fascicoli.json"),
        },
    )
    repository = OperationalResilienceRepository(sqlite_path=str(tmp_path / "operational.db"))

    report = run_operational_backup_plan(
        tenant_slug="studio-test",
        backup_manager=backup_manager,
        backup_dir=str(tmp_path / "backup"),
        repository=repository,
        trigger_source="test",
        schedule_code="nightly",
        local_mirror_dir=str(tmp_path / "mirror_cliente"),
        secondary_mirror_dir=str(tmp_path / "mirror_esterno"),
        secondary_label="Cartella cloud cliente",
    )

    assert report["success"] is True
    assert Path(report["report_path"]).exists()
    assert len(report["runs"]) == 1
    assert all(Path(run["local_copy_path"]).exists() for run in report["runs"])
    assert all(Path(run["secondary_copy_path"]).exists() for run in report["runs"])
    for run in report["runs"]:
        primary = Path(run["primary_path"])
        local_copy = Path(run["local_copy_path"])
        if primary.exists() and local_copy.exists():
            assert os.path.samefile(primary, local_copy)

    latest_backup = repository.latest_backup_run(tenant_slug="studio-test")
    assert latest_backup is not None
    assert latest_backup["payload_json"]["report_path"] == report["report_path"]


def test_operational_resilience_writer_redige_segreti(tmp_path: Path):
    path = tmp_path / "report.json"
    secret_key_field = "secret" + "_key"
    bootstrap_password_field = "BOOTSTRAP_ADMIN_" + "PASSWORD"

    _write_json(
        path,
        {
            "tenant_slug": "studio-test",
            secret_key_field: "valore-da-non-salvare",
            "runtime": {bootstrap_password_field: "admin"},
        },
    )

    content = path.read_text(encoding="utf-8")
    assert "valore-da-non-salvare" not in content
    assert '"secret_key": "[redatto]"' in content
    assert '"BOOTSTRAP_ADMIN_PASSWORD": "[redatto]"' in content


def test_crash_test_operativo_superficie_admin_renderizza(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    app = create_app(cfg)

    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "superadmin-operativo", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        response = client.get("/admin/crash-test-operativo", follow_redirects=True)

    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Crash test operativo" in html
    assert "Esegui crash test adesso" in html
    assert "Backup blindato" in html
    assert "Posso rompere il DB e il sistema non fa danni?" in html


def test_build_operational_crash_surface_legge_l_ultimo_backup_reale(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    app = create_app(cfg)

    with app.app_context():
        report = run_operational_backup_plan(
            tenant_slug="",
            backup_manager=GestioneBackup(
                directory_backup=app.config["BACKUP_DIR"],
                percorsi_dati={
                    "clienti": app.config["CLIENTI_DB"],
                    "fascicoli": app.config["FASCICOLI_DB"],
                },
            ),
            backup_dir=app.config["BACKUP_DIR"],
            repository=OperationalResilienceRepository(
                sqlite_path=str(Path(app.config["BACKUP_DIR"]) / "operational_resilience.db")
            ),
            trigger_source="test",
            schedule_code="nightly",
        )
        payload = build_operational_crash_surface()

    assert report["report_path"] == payload["latest_backup_report"]["report_path"]


def test_build_operational_crash_surface_non_espone_traceback_pubblici(tmp_path: Path, monkeypatch):
    cfg = _cfg_web(tmp_path)
    _write_studio_config(tmp_path / "config" / "studio.json")
    _seed_runtime(cfg)
    app = create_app(cfg)

    def _phase_con_traceback(selectors, **kwargs):
        return {
            "status": "failed",
            "return_code": 1,
            "duration_seconds": 0.1,
            "output_excerpt": 'Traceback (most recent call last):\n  File "segreto.py", line 1\nRuntimeError: percorso interno',
        }

    monkeypatch.setattr("pct.operational_resilience._run_pytest_phase", _phase_con_traceback)

    with app.app_context():
        repository = OperationalResilienceRepository(
            sqlite_path=str(Path(app.config["BACKUP_DIR"]) / "operational_resilience.db")
        )
        run_operational_crash_test(
            tenant_slug="",
            report_dir=str(Path(app.config["BACKUP_DIR"]) / "operational_crash_tests"),
            repair_dir=str(Path(app.config["BACKUP_DIR"]) / "repair_queue"),
            repository=repository,
            health_snapshot_factory=lambda: {
                "db": "ok",
                "scheduler": "ok",
                "ocr": "ok",
                "ai": "ok",
                "actions_required": [],
            },
            auto_repair=False,
            max_attempts=1,
            cwd=str(tmp_path),
        )
        payload = build_operational_crash_surface()

    payload_text = str(payload)
    assert "Traceback" not in payload_text
    assert "segreto.py" not in payload_text
    assert "Dettaglio tecnico disponibile solo nei log operativi riservati." in payload_text


def test_run_pytest_phase_usa_fallback_runtime_quando_pytest_non_e_disponibile(monkeypatch):
    monkeypatch.setattr("pct.operational_resilience._pytest_available", lambda: False)
    monkeypatch.setattr(
        "pct.operational_resilience._run_runtime_check",
        lambda check_id, **kwargs: {
            "status": "passed",
            "return_code": 0,
            "duration_seconds": 0.11,
            "output_excerpt": f"fallback runtime {check_id}",
        },
    )

    outcome = _run_pytest_phase(
        ("tests/e2e/test_studio_reale_flow.py",),
        fallback_check_id="business_flow",
        runtime_context={"base_config": {}},
    )

    assert outcome["status"] == "passed"
    assert "Pytest non disponibile nel runtime" in outcome["output_excerpt"]
    assert "fallback runtime business_flow" in outcome["output_excerpt"]
