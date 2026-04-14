from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.legal_intelligence import GestioneLegalIntelligence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Esporta i repository telematici strutturati per Lex.",
    )
    parser.add_argument(
        "--db-path",
        default="./intelligence/legal_intelligence.json",
        help="Percorso del database JSON legal_intelligence.",
    )
    parser.add_argument(
        "--normative-db-path",
        default="",
        help="Percorso opzionale delle tabelle normative.",
    )
    parser.add_argument(
        "--output-dir",
        default="telematico",
        help="Cartella di destinazione per i JSON esportati.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    gestore = GestioneLegalIntelligence(
        db_path=args.db_path,
        normative_db_path=args.normative_db_path or None,
    )
    export_dir = Path(args.output_dir)
    paths = gestore.export_telematico_repositories(str(export_dir))
    stats = gestore.statistiche_telematico_repository()

    print(f"Repository: {paths.get('repository', '')}")
    print(f"Snapshot: {paths.get('catalog_snapshot', '')}")
    print(f"Metodi: {paths.get('methods', '')}")
    print(f"WSDL: {paths.get('wsdl_modules', '')}")
    print(f"XSD: {paths.get('xsd_channels', '')}")
    print(f"Fonti catalogo: {paths.get('catalog_sources', '')}")
    print(f"Fonti telematiche: {paths.get('sources', '')}")
    print(f"Capabilities: {paths.get('capabilities', '')}")
    print(f"Regole: {paths.get('rules', '')}")
    print(f"Azioni: {paths.get('actions', '')}")
    print(f"Wizard PST: {paths.get('wizard_sections', '')}")
    print(f"Monitoraggio: {paths.get('monitoring', '')}")
    print(
        "Statistiche: "
        f"{stats.get('telematico_methods_repository', 0)} metodi, "
        f"{stats.get('telematico_xsd_channels_repository', 0)} canali XSD, "
        f"{stats.get('telematico_sources_repository', 0)} fonti, "
        f"{stats.get('telematico_actions_repository', 0)} azioni."
    )


if __name__ == "__main__":
    main()
