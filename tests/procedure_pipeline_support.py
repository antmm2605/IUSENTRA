from __future__ import annotations

import json
from pathlib import Path

from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig
from pct.procedure_inventory_importer import import_xsd_objects
from pct.procedure_lifecycle import generate_lifecycle_templates_for_catalog
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository
from pct.procedure_xsd_mapper import map_all_xsd_objects


def make_repo(tmp_path: Path) -> ProcedureLifecycleRepository:
    repo = ProcedureLifecycleRepository(CoverageSqliteConfig(str(tmp_path / "coverage.db")))
    repo.ensure_extended_schema()
    return repo


def write_catalog(tmp_path: Path) -> Path:
    catalog = {
        "versione": "test-xsd",
        "fonte": {
            "nome": "PST Test",
            "url": "https://pst.giustizia.it/PST/it/download.page",
            "fileFontePrevalente": "tipi-base.xsd",
        },
        "areas": [
            {
                "area": "procedimenti_speciali_sommari",
                "label": "Procedimenti speciali sommari",
                "items": [
                    {
                        "codice": "010",
                        "label": "Procedimento di ingiunzione ante causam",
                        "children": [{"codice": "010001", "label": "Ingiunzione test"}],
                    },
                    {"codice": "100", "label": "Item senza children"},
                    {"codice": "030", "label": "Sfratto", "children": [{"codice": "030001", "label": "Sfratto test"}]},
                    {"codice": "011", "label": "Cautelare", "children": [{"codice": "011001", "label": "Sequestro"}]},
                    {"codice": "020", "label": "Possessorio", "children": [{"codice": "020001", "label": "Possessorio"}]},
                    {"codice": "050", "label": "Ingiunzione societaria", "children": [{"codice": "050001", "label": "Ingiunzione societaria"}]},
                ],
            }
        ],
    }
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    return path


def seed_inventory(repo: ProcedureLifecycleRepository, tmp_path: Path) -> Path:
    path = write_catalog(tmp_path)
    import_xsd_objects(repo, str(path), dry_run=False)
    map_all_xsd_objects(repo, dry_run=False)
    generate_lifecycle_templates_for_catalog(repo, dry_run=False)
    return path
