"""Circolari e risoluzioni dell'Agenzia delle Entrate, circolari e messaggi dell'INPS: recupero in sfondo con ripresa.

Uso: nice -n 19 python scripts/prassi_recupero.py --archivio prassi.sqlite [--tratto 1800] [--pausa 2]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from pct.prassi.archivio import ArchivioPrassi  # noqa: E402
from pct.prassi.recupero import esegui_tratto  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archivio", required=True)
    ap.add_argument("--tratto", type=float, default=1800)
    ap.add_argument("--pausa", type=float, default=2.0)
    args = ap.parse_args()
    archivio = ArchivioPrassi(args.archivio)
    sessione = requests.Session()
    sessione.headers["User-Agent"] = "IUSENTRA archivio prassi (consultazione professionale)"
    while True:
        esito = esegui_tratto(archivio, lambda url: sessione.get(url, timeout=120), tempo_massimo=args.tratto, pausa=args.pausa)
        print(json.dumps(esito, ensure_ascii=False), flush=True)
        if not esito["testi_nuovi"] and not any(esito["elenchi"].values()):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
