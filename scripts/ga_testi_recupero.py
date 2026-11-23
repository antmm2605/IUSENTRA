"""Testo integrale delle sentenze del Consiglio di Stato, del CGA e dei TAR dal sito ufficiale, in sfondo e con ripresa.

Uso: nice -n 19 python scripts/ga_testi_recupero.py --catalogo catalogo.db --archivio ga_testi.sqlite [--tratto 1800]
Gli estremi vengono dal catalogo OpenGA (pct/giustizia_amministrativa_testi.py); ogni tratto legge i testi in coda.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests  # noqa: E402

from pct.giustizia_amministrativa_testi import ArchivioTestiGA, leggi  # noqa: E402


def estremi(catalogo: str):
    conn = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # Tutte le sentenze: la coda le legge per priorità (Consiglio di Stato, CGA, poi TAR), dalle più recenti.
    for riga in conn.execute("SELECT sede, nome_sede, tipo, numero, anno, ricorso, oggetto, esito_originale AS esito FROM righe "
                             "WHERE tipo LIKE 'SENTENZA%'"):
        yield dict(riga)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalogo", required=True)
    ap.add_argument("--archivio", required=True)
    ap.add_argument("--tratto", type=float, default=1800)
    ap.add_argument("--pausa", type=float, default=2.0)
    args = ap.parse_args()
    archivio = ArchivioTestiGA(args.archivio)
    print(json.dumps({"estremi_nuovi": archivio.carica_estremi(estremi(args.catalogo))}), flush=True)
    sessione = requests.Session()
    sessione.headers["User-Agent"] = "IUSENTRA archivio giurisprudenza (consultazione professionale)"
    while True:
        inizio = time.monotonic()
        esito = leggi(archivio, scarica=lambda url: sessione.get(url, timeout=60), tempo_massimo=args.tratto, pausa=args.pausa)
        print(json.dumps({**esito, "durata_s": round(time.monotonic() - inizio), "stati": archivio.conteggi()}), flush=True)
        if not esito["letti"] and not esito["errori"]:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
