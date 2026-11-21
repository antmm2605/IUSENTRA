"""Collega gli atti normativi della Gazzetta al testo della biblioteca Normattiva (pct/gazzetta/da_normattiva.py).

Uso: python scripts/gazzetta_testi_da_normattiva.py --archivio gazzetta_ufficiale.sqlite --normattiva normattiva.sqlite
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.gazzetta.archivio import ArchivioGazzetta  # noqa: E402
from pct.gazzetta.da_normattiva import collega  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archivio", required=True)
    ap.add_argument("--normattiva", required=True)
    args = ap.parse_args()
    print(json.dumps(collega(ArchivioGazzetta(args.archivio), args.normattiva), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
