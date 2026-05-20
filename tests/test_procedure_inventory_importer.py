from __future__ import annotations

import json
import subprocess
import sys

from pct.procedure_inventory_importer import import_xsd_objects, iter_xsd_objects, load_catalog
from tests.procedure_pipeline_support import make_repo, write_catalog


def test_importer_importa_children_item_senza_children_ed_e_idempotente(tmp_path):
    repo = make_repo(tmp_path)
    catalog_path = write_catalog(tmp_path)
    catalog = load_catalog(str(catalog_path))
    rows = iter_xsd_objects(catalog)

    assert {row["xsd_code"] for row in rows} >= {"010001", "100"}
    assert next(row for row in rows if row["xsd_code"] == "100")["xsd_family_code"] == "100"

    dry = import_xsd_objects(repo, str(catalog_path), dry_run=True)
    assert dry.imported == 0

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
        [
            sys.executable,
            "-m",
            "pct.procedure_inventory_importer",
            "--db",
            str(db_path),
            "--catalog",
            str(catalog_path),
            "--dry-run",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(dry.stdout)["dry_run"] is True

    applied = subprocess.run(
        [
            sys.executable,
            "-m",
            "pct.procedure_inventory_importer",
            "--db",
            str(db_path),
            "--catalog",
            str(catalog_path),
            "--apply",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(applied.stdout)["imported"] == 6
