"""Precarica e verifica i certificati PST .cer per la cifratura Atto.enc."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.pst_cifratura import (  # noqa: E402
    esegui_controllo_settimanale_certificati_cifratura,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlla e aggiorna i certificati pubblici PST di cifratura."
    )
    parser.add_argument("--cache-dir", default="", help="Cartella cache tecnica .cer.")
    parser.add_argument("--report-json", default="", help="Percorso report JSON.")
    parser.add_argument("--limit", type=int, default=0, help="Limite uffici per test mirati.")
    parser.add_argument(
        "--codice-ufficio",
        action="append",
        default=[],
        help="Controlla uno specifico codice ufficio PST; ripetibile.",
    )
    parser.add_argument(
        "--no-force-refresh",
        action="store_true",
        help="Usa la cache valida esistente senza riscaricare ogni certificato.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Esce con codice 2 se anche un solo certificato non viene verificato.",
    )
    args = parser.parse_args(argv)

    report = esegui_controllo_settimanale_certificati_cifratura(
        cache_dir=args.cache_dir or None,
        report_path=args.report_json or None,
        force_refresh=not args.no_force_refresh,
        limit=args.limit or None,
        codici_ufficio=args.codice_ufficio or None,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.strict and not report.get("ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
