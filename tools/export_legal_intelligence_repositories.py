from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.legal_intelligence import GestioneLegalIntelligence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Esporta i repository strutturati di legal intelligence per Lex.",
    )
    parser.add_argument(
        "--db-path",
        default="./intelligence/legal_intelligence.json",
        help="Percorso del database JSON legal intelligence.",
    )
    parser.add_argument(
        "--normative-db-path",
        default="",
        help="Percorso opzionale del database tabelle normative.",
    )
    parser.add_argument(
        "--output-dir",
        default="legal_intelligence",
        help="Cartella di output per i repository JSON esportati.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gestore = GestioneLegalIntelligence(
        str(Path(args.db_path).resolve()),
        normative_db_path=str(Path(args.normative_db_path).resolve()) if args.normative_db_path else None,
    )
    paths = gestore.export_legal_repositories(args.output_dir or None)
    stats = gestore.statistiche_repository()

    for key, path in paths.items():
        print(f"{key}: {path}")
    print(
        "Statistiche: "
        f"{stats.get('legal_sources_repository', 0)} fonti, "
        f"{stats.get('legal_engines_repository', 0)} motori, "
        f"{stats.get('legal_keyword_to_engine', 0)} routing keyword->motore, "
        f"{stats.get('legal_keyword_to_source', 0)} routing keyword->fonte, "
        f"{stats.get('legal_engine_source_edges', 0)} edge motore-fonte, "
        f"{stats.get('legal_monitoring_repository', 0)} snapshot monitoraggio, "
        f"{stats.get('legal_alert_repository', 0)} alert, "
        f"{stats.get('legal_audit_repository', 0)} audit."
    )


if __name__ == "__main__":
    main()
