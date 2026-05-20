from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pct.procedure_inventory_importer import (
    DEFAULT_CATALOG_PATH,
    import_xsd_objects,
    iter_xsd_objects,
    load_catalog,
    write_import_report,
)
from tests.procedure_pipeline_support import make_repo, write_catalog


def _cli_command(*args: str) -> list[str]:
    module_runner = (
        "import sys; "
        f"sys.path.insert(0, {str(Path.cwd())!r}); "
        "from pct.procedure_inventory_importer import main; "
        "raise SystemExit(main(sys.argv[1:]))"
    )
    return [sys.executable, "-c", module_runner, *args]


def test_importer_importa_children_item_senza_children_ed_e_idempotente(tmp_path):
    repo = make_repo(tmp_path)
    catalog_path = write_catalog(tmp_path)
    catalog = load_catalog(str(catalog_path))
    rows = iter_xsd_objects(catalog)

    assert {row["xsd_code"] for row in rows} >= {"010001", "100"}
    assert next(row for row in rows if row["xsd_code"] == "100")["xsd_family_code"] == "100"

    dry = import_xsd_objects(repo, str(catalog_path), dry_run=True)
    assert dry.imported == 0
    report_path = write_import_report(dry, tmp_path / "report.json")
    assert json.loads(report_path.read_text(encoding="utf-8"))["dry_run"] is True

    applied = import_xsd_objects(repo, str(catalog_path), dry_run=False)
    assert applied.imported == applied.total_catalog_objects
    assert repo.get_xsd_object("010001")["xsd_area_code"] == "procedimenti_speciali_sommari"
    assert repo.list_audit_log("legal_ministerial_xsd_objects")

    second = import_xsd_objects(repo, str(catalog_path), dry_run=False)
    assert second.unchanged == second.total_catalog_objects

    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    payload["areas"][0]["items"][0]["children"][0]["label"] = "Ingiunzione aggiornata"
    catalog_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    updated = import_xsd_objects(repo, str(catalog_path), dry_run=False)
    assert updated.updated == 1
    assert repo.get_xsd_object("010001")["xsd_label"] == "Ingiunzione aggiornata"


def test_cli_importer_dry_run_e_apply_restituisce_json(tmp_path):
    db_path = tmp_path / "cli.db"
    catalog_path = write_catalog(tmp_path)

    dry = subprocess.run(
        _cli_command(
            "--db",
            str(db_path),
            "--catalog",
            str(catalog_path),
            "--report",
            str(tmp_path / "dry-report.json"),
            "--dry-run",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(dry.stdout)["dry_run"] is True
    assert (tmp_path / "dry-report.json").exists()

    applied = subprocess.run(
        _cli_command(
            "--db",
            str(db_path),
            "--catalog",
            str(catalog_path),
            "--report",
            str(tmp_path / "apply-report.json"),
            "--apply",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(applied.stdout)["imported"] == 6
    assert json.loads((tmp_path / "apply-report.json").read_text(encoding="utf-8"))["imported"] == 6

    default_dry = subprocess.run(
        _cli_command(
            "--db",
            str(tmp_path / "default-cli.db"),
            "--report",
            str(tmp_path / "default-report.json"),
            "--dry-run",
        ),
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(default_dry.stdout)["catalog_path"].endswith("pratiche_collegate_catalog.json")
    assert DEFAULT_CATALOG_PATH.exists()
