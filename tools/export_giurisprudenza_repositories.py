from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.giurisprudenza import GestioneGiurisprudenza


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Esporta i repository strutturati di giurisprudenza per Lex.",
    )
    parser.add_argument(
        "--db-path",
        default="./intelligence/giurisprudenza.json",
        help="Percorso del database JSON giurisprudenza.",
    )
    parser.add_argument(
        "--output-dir",
        default="giurisprudenza",
        help="Cartella di output per i repository JSON esportati.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gestore = GestioneGiurisprudenza(str(Path(args.db_path).resolve()))
    paths = gestore.export_giurisprudenza_repositories(args.output_dir or None)
    stats = gestore.statistiche_repository()

    for key, path in paths.items():
        print(f"{key}: {path}")
    print(
        "Statistiche: "
        f"{stats.get('giurisprudenza_sources_repository', 0)} fonti, "
        f"{stats.get('giurisprudenza_taxonomy_repository', 0)} nodi tassonomici, "
        f"{stats.get('giurisprudenza_usage_policy_repository', 0)} policy d'uso, "
        f"{stats.get('giurisprudenza_sync_registry', 0)} righe sync."
    )


if __name__ == "__main__":
    main()
