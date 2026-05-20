"""Import controllato del catalogo PST/XSD nel registro ministeriale IUSENTRA."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from pct.legal_coverage_sqlite_repository import CoverageSqliteConfig
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository, json_dumps

DEFAULT_CATALOG_PATH = Path("pct") / "data" / "pratiche_collegate_catalog.json"
DEFAULT_REPORT_PATH = Path("artifacts") / "procedure-lifecycle" / "xsd_import_report.json"


@dataclass(frozen=True)
class ImportReport:
    catalog_path: str
    dry_run: bool
    total_catalog_objects: int
    created: int
    updated: int
    unchanged: int
    imported: int
    missing: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load_catalog(path: str) -> dict[str, Any]:
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalogo XSD non trovato: {catalog_path}")
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Il catalogo XSD deve essere un oggetto JSON.")
    return payload


def compute_import_hash(row: dict[str, Any]) -> str:
    payload = {key: value for key, value in row.items() if key != "import_hash"}
    return hashlib.sha256(json_dumps(payload).encode("utf-8")).hexdigest()


def iter_xsd_objects(catalog: dict[str, Any]) -> list[dict[str, Any]]:
    fonte = dict(catalog.get("fonte") or {})
    source_version = _clean(catalog.get("versione")) or "unknown"
    source_name = _clean(fonte.get("nome")) or "PST/XSD"
    source_url = _clean(fonte.get("url"))
    source_file = _clean(fonte.get("fileFontePrevalente"))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for area in catalog.get("areas") or []:
        area_code = _clean(area.get("area"))
        area_label = _clean(area.get("label"))
        for item in area.get("items") or []:
            family_code = _clean(item.get("codice"))
            family_label = _clean(item.get("label"))
            children = list(item.get("children") or [])
            if not children:
                children = [{"codice": family_code, "label": family_label}]
            for child in children:
                xsd_code = _clean(child.get("codice"))
                if not xsd_code or xsd_code in seen:
                    continue
                row = {
                    "xsd_code": xsd_code,
                    "xsd_label": _clean(child.get("label")) or family_label or xsd_code,
                    "xsd_area_code": area_code,
                    "xsd_area_label": area_label,
                    "xsd_family_code": family_code or None,
                    "xsd_family_label": family_label or None,
                    "source_version": source_version,
                    "source_name": source_name,
                    "source_url": source_url or None,
                    "source_file": source_file or None,
                    "active": 1,
                    "last_verified_at": None,
                    "notes": "Import da catalogo PST/XSD; item senza children importati come codice depositabile autonomo."
                    if not item.get("children")
                    else None,
                }
                row["import_hash"] = compute_import_hash(row)
                rows.append(row)
                seen.add(xsd_code)
    return rows


def import_xsd_objects(
    repo: ProcedureLifecycleRepository,
    catalog_path: str,
    dry_run: bool = True,
) -> ImportReport:
    catalog = load_catalog(catalog_path)
    rows = iter_xsd_objects(catalog)
    created = updated = unchanged = imported = 0
    missing: list[str] = []

    db_exists = Path(str(repo.config.path or "")).exists()
    table_ready = repo.table_exists("legal_ministerial_xsd_objects") if dry_run and db_exists else not dry_run
    if not dry_run:
        repo.ensure_extended_schema()

    for row in rows:
        before = repo.get_xsd_object(row["xsd_code"]) if table_ready else None
        if before is None:
            created += 1
        elif before.get("import_hash") == row.get("import_hash"):
            unchanged += 1
        else:
            updated += 1
        if dry_run:
            continue
        repo.upsert_xsd_object(row)
        imported += 1

    if not dry_run:
        imported_codes = {item["xsd_code"] for item in repo.list_xsd_objects()}
        missing = [row["xsd_code"] for row in rows if row["xsd_code"] not in imported_codes]

    return ImportReport(
        catalog_path=str(Path(catalog_path)),
        dry_run=dry_run,
        total_catalog_objects=len(rows),
        created=created,
        updated=updated,
        unchanged=unchanged,
        imported=imported,
        missing=missing,
    )


def write_import_report(report: ImportReport, report_path: str | Path = DEFAULT_REPORT_PATH) -> Path:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Importa il catalogo PST/XSD nel registro ministeriale IUSENTRA.")
    parser.add_argument("--db", required=True, help="Percorso SQLite legal_coverage.db")
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG_PATH),
        help="Percorso pct/data/pratiche_collegate_catalog.json",
    )
    parser.add_argument(
        "--report",
        default=str(DEFAULT_REPORT_PATH),
        help="Percorso report JSON import XSD",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Analizza senza scrivere record")
    mode.add_argument("--apply", action="store_true", help="Applica l'import nel database")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    dry_run = not bool(args.apply)
    repo = ProcedureLifecycleRepository(CoverageSqliteConfig(str(args.db)))
    report = import_xsd_objects(repo, str(args.catalog), dry_run=dry_run)
    write_import_report(report, args.report)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - coperto tramite main() nei test CLI.
    raise SystemExit(main())
