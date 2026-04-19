from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from pct.cli import cli
from pct.tenant import GestioneTenant
from tests.test_storage_postgres_migration import _seed_core_json
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.migration_assistant import build_migration_assistant, execute_migration_assistant


def _json_from_output(output: str) -> dict:
    start = output.find("{")
    if start < 0:
        return {}
    return json.loads(output[start:])


def test_tenant_migration_full_snapshot_diff_e_rollback_sono_reali(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Migrazione E2E", "studio-migrazione-e2e", db_config={"mode": "JSON"})
    _seed_core_json(tm.percorsi_dati(studio.slug))
    app = create_app(cfg)

    with app.app_context():
        report = execute_migration_assistant(selected_slug=studio.slug, target="sqlite")
        payload = build_migration_assistant(selected_slug=studio.slug)

    assert report["target"] == "sqlite"
    assert report["success"] is True
    assert Path(report["report_path"]).exists()
    assert Path(report["pre_migration_snapshot_path"]).exists()
    assert report["precheck_snapshot"]["snapshot_path"] == report["pre_migration_snapshot_path"]
    assert report["diff_summary"]["by_domain"]["clienti"]["prima"] == 1
    assert report["diff_summary"]["by_domain"]["clienti"]["dopo"] == 1
    assert report["rollback"]["command"] == f"iusentra migrate --tenant={studio.slug} --rollback"
    assert report["rollback"]["context"]["previous_database_config"]["mode"] == "JSON"
    assert payload["last_execution"] is not None
    assert payload["last_execution"]["rollback"]["command"]

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "migrate",
            "--rollback",
            f"--tenant={studio.slug}",
            f"--registry={cfg['TENANTS_REGISTRY']}",
        ],
    )

    assert result.exit_code == 0
    rollback_payload = _json_from_output(result.output)
    assert rollback_payload["success"] is True
    assert Path(rollback_payload["report_path"]).exists()

    studio_after = tm.get(studio.slug)
    assert studio_after is not None
    assert studio_after.database.normalized_mode == "JSON"
    assert studio_after.database.effective_runtime_kind == "json"
