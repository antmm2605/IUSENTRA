from __future__ import annotations

from pathlib import Path

from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.migration_assistant import build_migration_assistant, execute_migration_assistant


def test_tenant_migration_full_generates_snapshot_diff_rollback_and_log(tmp_path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    tm = GestioneTenant(cfg["TENANTS_REGISTRY"])
    studio = tm.crea("Studio Migrazione E2E", "studio-migrazione-e2e", db_config={"mode": "SQLITE"})
    app = create_app(cfg)

    with app.app_context():
        report = execute_migration_assistant(selected_slug=studio.slug, target="sqlite")
        payload = build_migration_assistant(selected_slug=studio.slug)

    assert report["target"] == "sqlite"
    assert report["success"] is True
    assert report["report_path"]
    assert Path(report["report_path"]).exists()
    assert report["precheck_snapshot"]["source_label"] == "JSON legacy"
    assert report["rollback"]["status"] in {"success", "warning"}
    assert report["diff_summary"]["summary"]["rows_total"] >= 1
    assert report["operation_log"]
    assert payload["last_execution"] is not None
    assert payload["last_execution"]["precheck_snapshot"]["backup_dir"]
    assert payload["last_execution"]["operation_log"]
