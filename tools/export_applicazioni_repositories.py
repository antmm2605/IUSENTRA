from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.applicazioni_repository import (
    GestioneApplicazioniRepository,
    default_applicazioni_repository_db_path,
    derive_applicazioni_access_json_path,
    derive_applicazioni_catalog_json_path,
    derive_applicazioni_featured_json_path,
    derive_applicazioni_repository_json_path,
    derive_applicazioni_section_kinds_json_path,
    derive_applicazioni_sections_json_path,
    derive_applicazioni_statistics_json_path,
    derive_applicazioni_status_json_path,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Esporta i repository strutturati delle applicazioni per Lex.",
    )
    parser.add_argument(
        "--db-path",
        default=default_applicazioni_repository_db_path(),
        help="Percorso del database SQLite del repository applicazioni.",
    )
    parser.add_argument(
        "--output-dir",
        default="applicazioni",
        help="Cartella di output per i repository JSON esportati.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    db_path = str(Path(args.db_path).resolve())
    repository = GestioneApplicazioniRepository(
        db_path,
        json_path=derive_applicazioni_repository_json_path(db_path),
        sections_json_path=derive_applicazioni_sections_json_path(db_path),
        catalog_json_path=derive_applicazioni_catalog_json_path(db_path),
        statuses_json_path=derive_applicazioni_status_json_path(db_path),
        access_json_path=derive_applicazioni_access_json_path(db_path),
        section_kinds_json_path=derive_applicazioni_section_kinds_json_path(db_path),
        featured_json_path=derive_applicazioni_featured_json_path(db_path),
        statistics_json_path=derive_applicazioni_statistics_json_path(db_path),
    )
    repository.synchronize_runtime(export_json=True)
    paths = repository.export_split_jsons(args.output_dir or None)
    stats = repository.storage_stats()

    for key, path in paths.items():
        print(f"{key}: {path}")
    print(
        "Statistiche: "
        f"{stats.get('applicazioni_catalog_repository', 0)} moduli, "
        f"{stats.get('applicazioni_sections_repository', 0)} sezioni, "
        f"{stats.get('applicazioni_status_repository', 0)} stati, "
        f"{stats.get('applicazioni_access_repository', 0)} modalita, "
        f"{stats.get('applicazioni_featured_repository', 0)} voci primo piano."
    )


if __name__ == "__main__":
    main()
