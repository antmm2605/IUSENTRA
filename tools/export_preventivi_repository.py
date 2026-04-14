from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.preventivi import GestionePreventivi


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Esporta il repository strutturato dei preventivi per Lex.",
    )
    parser.add_argument(
        "--db-path",
        default="./preventivi/preventivi.json",
        help="Percorso del database JSON dei preventivi.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Percorso del JSON repository completo. Se omesso usa il path derivato dal runtime.",
    )
    parser.add_argument(
        "--split-dir",
        default="",
        help="Cartella di export per repository, stati workflow, field map e regole.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    gestore = GestionePreventivi(str(Path(args.db_path).resolve()))
    repository_path = gestore.export_preventivi_repository(args.output or None)
    split_paths = gestore.export_preventivi_repository_split(args.split_dir or None)
    stats = gestore.statistiche_repository()

    print(f"Repository preventivi esportato in: {repository_path}")
    for key, path in split_paths.items():
        print(f"{key}: {path}")
    print(
        "Statistiche: "
        f"{stats.get('preventivi_workflow_states', 0)} stati workflow, "
        f"{stats.get('preventivi_field_map', 0)} campi, "
        f"{stats.get('preventivi_rules', 0)} regole, "
        f"{stats.get('preventivi_practice_catalog', 0)} pratiche, "
        f"{stats.get('preventivi_records', 0)} preventivi, "
        f"{stats.get('conferimenti_records', 0)} conferimenti."
    )


if __name__ == "__main__":
    main()
