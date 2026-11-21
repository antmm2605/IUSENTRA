"""Recupero storico della Gazzetta Ufficiale dal 01/01/2022, in sfondo, fino al completamento.

Ripete i tratti di ``pct.gazzetta.storico.esegui_tratto`` (sommari mancanti, poi testi completi degli atti) con la
pausa gentile fra le richieste; lo stato è nell'archivio, quindi fermato e rilanciato riprende da dove era.
Lo stesso recupero gira anche da solo nel lavoro pianificato «Gazzetta Ufficiale: sommari delle sei serie».

Uso (a bassa priorità): nice -n 19 ionice -c 3 python scripts/gazzetta_recupero_storico.py --archivio FILE
    [--pausa 2] [--tratto 1800] [--solo-sommari] [--una-volta]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from pct.gazzetta.acquisizione import esegui_giro  # noqa: E402
from pct.gazzetta.archivio import ArchivioGazzetta  # noqa: E402
from pct.gazzetta.storico import PAUSA_GENTILE, esegui_tratto  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archivio", required=True)
    ap.add_argument("--pausa", type=float, default=PAUSA_GENTILE)
    ap.add_argument("--tratto", type=float, default=1800.0)
    ap.add_argument("--solo-sommari", action="store_true")
    ap.add_argument("--una-volta", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    archivio = ArchivioGazzetta(args.archivio)
    while True:
        inizio = time.monotonic()
        giro = esegui_giro(archivio, pausa=args.pausa)
        esito = esegui_tratto(archivio, tempo_massimo=args.tratto, pausa=args.pausa, con_testi=not args.solo_sommari)
        riepilogo = {
            "quando": esito["eseguito_il"], "durata_s": round(time.monotonic() - inizio),
            "giro_30_giorni": giro["fascicoli_nuovi"],
            "sommari": {k: v for k, v in esito["sommari"].items() if k != "errori"},
            "errori_sommari": esito["sommari"]["errori"][:5],
            "testi": esito["testi"], "copertura": esito["copertura"],
        }
        print(json.dumps(riepilogo, ensure_ascii=False), flush=True)
        finito = esito["sommari"]["completo"] and (args.solo_sommari or esito["testi"]["completo"])
        # Nulla di nuovo in un tratto intero (solo errori ripetuti del sito): ci pensa il lavoro pianificato.
        fermo = not esito["sommari"]["fascicoli_nuovi"] and not esito["testi"]["testi_nuovi"] and not giro["fascicoli_nuovi"]
        if args.una_volta or finito or fermo:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
