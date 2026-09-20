#!/usr/bin/env python3
"""Toglie da `dati_json` le collezioni che hanno gia' una colonna propria.

Fino alla 2.327.1 ogni fascicolo veniva salvato due volte: `dati_json`
conteneva il fascicolo intero — documenti, attivita' e depositi compresi — e
le stesse tre collezioni stavano anche in `documenti_json`, `attivita_json` e
`scadenze_json`. Ogni lettura dell'archivio pagava l'archivio documentale due
volte.

Dalla 2.328.0 la colonna e' la fonte e `dati_json` non le duplica piu'. Le
righe scritte prima restano leggibili senza toccare niente — la lettura
prende sempre le collezioni dalle colonne — ma continuano a pesare il doppio
finche' non vengono riscritte. Questo script le riscrive.

Senza `--applica` non modifica nulla: dice soltanto quanto spazio e'
occupato dalla copia in eccesso.

    python scripts/snellisci_dati_json_fascicoli.py --data-root /data
    python scripts/snellisci_dati_json_fascicoli.py --data-root /data --applica
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Eseguito come script dalla radice del repository: `pct` deve essere trovabile.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _riga(esito: dict) -> str:
    return (
        f"{esito['studio']:30s} {esito['fascicoli']:5d} fascicoli, "
        f"{esito['da_sgrassare']:5d} da sgrassare, {esito['mb_in_eccesso']:7.1f} MB in eccesso"
        + (f"   riscritte {esito['riscritte']} righe" if esito["riscritte"] else "")
        + (f"   ERRORE: {esito['errore']}" if esito["errore"] else "")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="/data", help="Radice dati IUSENTRA.")
    parser.add_argument("--applica", action="store_true", help="Riscrive davvero; senza, e' solo un conteggio.")
    args = parser.parse_args(argv)

    # Stessa logica della console: una sola versione, nessuna deriva.
    from pct.manutenzione_dati_json import esamina_tutti

    esito = esamina_tutti(Path(args.data_root).expanduser(), riscrivi=args.applica)
    if not esito["studi"]:
        print(esito["messaggio"], file=sys.stderr)
        return 1
    for studio in esito["studi"]:
        print(_riga(studio))
    print(f"\n{esito['messaggio']}")
    if not args.applica and esito["mb_in_eccesso"]:
        print("Esegui con --applica per riscrivere. Le colonne fonte non vengono toccate.")
    return 0 if esito["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
