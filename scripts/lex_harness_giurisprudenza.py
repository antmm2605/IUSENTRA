"""Precalcola le pronunce per norma per la fase 5 dell'harness (lex/harness/dati/giurisprudenza_per_norma.json).

Per ogni norma del catalogo cerca nei corpus (Cassazione SentenzeWeb e archivio dello studio, in sola lettura) le
pronunce che la citano, con gli estremi e l'URL ufficiale. Si esegue fuori dalle richieste (di notte o a mano), dove i
corpus sono leggibili: nella richiesta l'harness legge solo il file. Una norma senza risultati resta con l'elenco vuoto
(«nessuna pronuncia trovata»), così la fase non torna a interrogare l'archivio.

Uso: python scripts/lex_harness_giurisprudenza.py [--solo chiave1,chiave2] [--secondi 120]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.harness.giurisprudenza import _PRECALCOLATE, archivi, cerca  # noqa: E402
from lex.harness.norme import NORME  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo", default="")
    ap.add_argument("--secondi", type=float, default=120.0)
    args = ap.parse_args()
    chiavi = [k for k in (args.solo.split(",") if args.solo else NORME) if k in NORME]
    sorgenti = archivi()
    indice = json.loads(_PRECALCOLATE.read_text(encoding="utf-8")) if _PRECALCOLATE.is_file() else {"norme": {}}
    for k in chiavi:
        n = NORME[k]
        esito = cerca(f"{n.citazione} {n.rubrica}", limite=3, secondi=args.secondi, sorgenti=lambda: sorgenti)
        if esito.errori and not esito.pronunce:
            print(f"{k}: non consultabile ({'; '.join(esito.errori)})")
            continue
        indice["norme"][k] = [vars(p) for p in esito.pronunce]
        print(f"{k}: {len(esito.pronunce)} pronunce")
    indice.update({"generato_il": date.today().strftime("%d/%m/%Y"), "archivi": [s for s, _ in sorgenti]})
    _PRECALCOLATE.write_text(json.dumps(indice, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
