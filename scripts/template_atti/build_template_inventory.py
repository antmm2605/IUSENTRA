"""Genera inventario STRICT Template Atti.

Uso:
    python scripts/template_atti/build_template_inventory.py
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pct.template_atti_inventory import (  # noqa: E402
    DEFAULT_REPORT_JSON,
    DEFAULT_REPORT_MD,
    build_template_inventory,
    export_template_inventory_report,
    template_inventory_stats,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Costruisce l'inventario STRICT dei Template Atti.")
    parser.add_argument("--data-root", default="", help="Data root tenant-aware da ispezionare.")
    parser.add_argument("--markdown", default=str(DEFAULT_REPORT_MD), help="Report Markdown da scrivere.")
    parser.add_argument("--json", default=str(DEFAULT_REPORT_JSON), help="Report JSON da scrivere.")
    args = parser.parse_args()

    source_records = build_template_inventory(args.data_root or None, include_source_duplicates=True)
    records = build_template_inventory(args.data_root or None)
    report = export_template_inventory_report(
        records,
        source_records=source_records,
        output_md=args.markdown,
        output_json=args.json,
    )
    stats = template_inventory_stats(records, source_records=source_records)

    print(f"Totale rilevato: {stats['detected_total']}")
    print(f"Record di fonte ispezionati: {stats['source_records_total']}")
    print(f"Totale atteso: {stats['expected_total']}")
    print(f"Scostamento: {stats['delta']}")
    print("Breakdown per fonte canonica:")
    for source, count in stats["breakdown_by_source"].items():
        print(f"  - {source}: {count}")
    print("Breakdown record di fonte:")
    for source, count in stats["breakdown_by_source_records"].items():
        print(f"  - {source}: {count}")
    print(f"Template senza Cartabia: {stats['missing_cartabia_profile']}")
    print(f"Template senza prefill: {stats['missing_prefill_bindings']}")
    print(f"Template senza timbro: {stats['missing_timbro_support']}")
    print(f"Template senza binding compilatore: {stats['missing_compiler_binding']}")
    print(f"Gruppi con copie multiple: {stats['duplicates']}")
    print(f"Template orfani/non raggiungibili UI: {stats['not_reachable_from_ui']}")
    print(f"Report Markdown: {Path(args.markdown).resolve()}")
    print(f"Report JSON: {Path(args.json).resolve()}")
    return 0 if report else 1


if __name__ == "__main__":
    raise SystemExit(main())
