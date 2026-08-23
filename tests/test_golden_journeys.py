from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pct.auth import GestioneUtenti
from pct.cli import cli
from pct.golden_journeys import (
    GOLDEN_JOURNEYS,
    WORKSPACE_DIRNAME,
    build_golden_journey_payload,
    prepare_synthetic_workspace,
    rollback_synthetic_workspace,
    run_golden_journeys,
)


def _workspace(tmp_path: Path) -> Path:
    return tmp_path / WORKSPACE_DIRNAME


def test_catalogo_contiene_esattamente_i_quindici_journey_p0():
    identifiers = [journey.journey_id for journey in GOLDEN_JOURNEYS]

    assert len(identifiers) == 15
    assert len(set(identifiers)) == 15
    assert all(journey.capability_ids for journey in GOLDEN_JOURNEYS)
    assert all(journey.pytest_selectors for journey in GOLDEN_JOURNEYS)
    assert all(journey.provider_status != "eseguito" for journey in GOLDEN_JOURNEYS)


def test_fixture_sintetica_crea_tenant_sqlite_ruoli_e_documenti_controllati(tmp_path):
    fixture = prepare_synthetic_workspace(workspace_dir=_workspace(tmp_path), run_id="run-fixture-a")

    assert fixture["source_of_truth"] == "sqlite"
    assert fixture["json_authoritative"] is False
    assert fixture["synthetic_password_stored"] is False
    assert {tenant["slug"] for tenant in fixture["tenants"]} == {"tenant-a", "tenant-b"}
    for tenant in fixture["tenants"]:
        assert Path(tenant["studio_db"]).exists()
        assert tenant["quick_check"] == "ok"
        assert {user["role"] for user in tenant["users"]} == {"AMMINISTRATORE", "AVVOCATO", "PRATICANTE"}
        assert set(tenant["document_names"]) == {
            "atto-controllato.pdf",
            "metadati-controllati.xml",
            "pec-controllata.eml",
            "busta-controllata.zip",
        }

    tenant_a = next(tenant for tenant in fixture["tenants"] if tenant["slug"] == "tenant-a")
    users = GestioneUtenti(
        db_path=str(Path(tenant_a["root"]) / "auth" / "utenti.json"),
        audit_path=str(Path(tenant_a["root"]) / "auth" / "audit.json"),
        secret_key="golden-journey-fixture",
        crea_admin_se_vuoto=False,
    )
    assert users.get_by_username("tenant-a-lettura").ha_permesso("fascicoli.scrivi") is False


def test_rollback_rifiuta_root_esterna_e_rimuove_soltanto_run_marcata(tmp_path):
    workspace = _workspace(tmp_path)
    fixture = prepare_synthetic_workspace(workspace_dir=workspace, run_id="run-rollback-a")
    result = rollback_synthetic_workspace(workspace_dir=workspace, run_id="run-rollback-a")

    assert result["ok"] is True
    assert not Path(fixture["run_root"]).exists()
    assert (workspace / ".iusentra-golden-journeys.json").exists()


def test_runner_persiste_report_per_tutti_i_quindici_journey(monkeypatch, tmp_path):
    class Result:
        returncode = 0
        stdout = "15 passed in 1.00s"
        stderr = ""

    def fake_run(command, **kwargs):
        assert command[:3] == [__import__("sys").executable, "-m", "pytest"]
        assert kwargs["env"]["IUSENTRA_GOLDEN_JOURNEY_WORKSPACE"].endswith("run-runner-a")
        return Result()

    monkeypatch.setattr("pct.golden_journeys.subprocess.run", fake_run)
    workspace = _workspace(tmp_path)
    report = run_golden_journeys(workspace_dir=workspace, cwd=str(tmp_path), run_id="run-runner-a")
    payload = build_golden_journey_payload(workspace_dir=workspace, report_payload=report)

    assert report["success"] is True
    assert len(report["journeys"]) == 15
    assert payload["summary"] == {
        "journeys_total": 15,
        "passed": 15,
        "failed": 0,
        "not_run": 0,
        "status": "passed",
        "provider_status": "non_eseguito",
        "source_of_truth": "sqlite",
    }
    persisted = json.loads(Path(report["report_path"]).read_text(encoding="utf-8"))
    assert persisted["fixture"]["synthetic_password_stored"] is False
    assert "FixtureSoloTest" not in Path(report["report_path"]).read_text(encoding="utf-8")


def test_cli_golden_journey_no_run_mostra_catalogo(tmp_path):
    result = CliRunner().invoke(cli, ["golden-journey", "--no-run", "--workspace", str(_workspace(tmp_path))])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["journeys_total"] == 15
    assert payload["summary"]["provider_status"] == "non_eseguito"


def test_cli_golden_journey_termina_con_errore_se_una_journey_fallisce(monkeypatch, tmp_path):
    report_path = tmp_path / "golden_journeys_latest.json"
    report = {
        "success": False,
        "report_path": str(report_path),
        "fixture": {"run_id": "run-cli-failure"},
    }
    monkeypatch.setattr("pct.cli.run_golden_journeys", lambda **_kwargs: report)
    monkeypatch.setattr(
        "pct.cli.build_golden_journey_payload",
        lambda **_kwargs: {"summary": {"status": "failed"}},
    )

    result = CliRunner().invoke(cli, ["golden-journey", "--workspace", str(_workspace(tmp_path))])

    assert result.exit_code != 0
    assert "golden journey non hanno superato" in result.output
