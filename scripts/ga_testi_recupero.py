"""Testo integrale delle sentenze del Consiglio di Stato, del CGA e dei TAR dal sito ufficiale, in sfondo e con ripresa.

Uso: nice -n 19 python scripts/ga_testi_recupero.py --catalogo catalogo.db --archivio ga_testi.sqlite [--tratto 1800]
     [--studio-db studio.db | --uffici-studio uffici.txt]
Gli estremi vengono dal catalogo OpenGA (pct/giustizia_amministrativa_testi.py); ogni tratto legge i testi in coda.
Ordine della coda: Consiglio di Stato, CGA, TAR Calabria e Lazio, TAR delle sedi dei fascicoli dello studio (dagli
uffici dei fascicoli, letti in sola lettura), altre sedi; ultimi tre anni prima; sentenze brevi in fondo.
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

from pct.giustizia_amministrativa_testi import ArchivioTestiGA, leggi, sedi_dai_fascicoli  # noqa: E402


def estremi(catalogo: str):
    conn = sqlite3.connect(f"file:{catalogo}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    # Tutte le sentenze: la coda le legge per priorità (Consiglio di Stato, CGA, poi TAR), dalle più recenti.
    for riga in conn.execute("SELECT sede, nome_sede, tipo, numero, anno, ricorso, oggetto, esito_originale AS esito FROM righe "
                             "WHERE tipo LIKE 'SENTENZA%'"):
        yield dict(riga)


def uffici_dei_fascicoli(studio_db: str) -> list[str]:
    conn = sqlite3.connect(f"file:{studio_db}?mode=ro", uri=True, timeout=60)
    try:
        return [str(r[0]) for r in conn.execute("SELECT DISTINCT tribunale FROM fascicoli WHERE COALESCE(tribunale, '') <> ''")]
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalogo", required=True)
    ap.add_argument("--archivio", required=True)
    ap.add_argument("--tratto", type=float, default=1800)
    ap.add_argument("--pausa", type=float, default=2.0)
    ap.add_argument("--studio-db", help="studio.db dello studio, letto in sola lettura per le sedi dei fascicoli")
    ap.add_argument("--uffici-studio", help="file di testo con un ufficio dei fascicoli per riga (in alternativa)")
    args = ap.parse_args()
    archivio = ArchivioTestiGA(args.archivio)
    uffici = (uffici_dei_fascicoli(args.studio_db) if args.studio_db else
              Path(args.uffici_studio).read_text(encoding="utf-8").splitlines() if args.uffici_studio else None)
    if uffici is not None:
        archivio.imposta_sedi_studio(sedi_dai_fascicoli(uffici), da=args.studio_db or args.uffici_studio)
    print(json.dumps({"sedi_studio": sorted(archivio.sedi_studio()), "riordinati": archivio.riordina()}), flush=True)
    print(json.dumps({"estremi_nuovi": archivio.carica_estremi(estremi(args.catalogo))}), flush=True)
    sessione = requests.Session()
    sessione.headers["User-Agent"] = "IUSENTRA archivio giurisprudenza (consultazione professionale)"
    while True:
        inizio = time.monotonic()
        esito = leggi(archivio, scarica=lambda url: sessione.get(url, timeout=60), tempo_massimo=args.tratto, pausa=args.pausa)
        print(json.dumps({**esito, "durata_s": round(time.monotonic() - inizio), "stati": archivio.conteggi()}), flush=True)
        if not esito["letti"] and not esito["errori"] and not esito.get("da_ritentare"):
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
