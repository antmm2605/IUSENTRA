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
import json
import sqlite3
import sys
from pathlib import Path


def _studio_db_dei_tenant(data_root: Path) -> list[Path]:
    radice = data_root / "tenants"
    if not radice.exists():
        locale = data_root / "studio.db"
        return [locale] if locale.exists() else []
    trovati = []
    for cartella in sorted(p for p in radice.iterdir() if p.is_dir()):
        db = cartella / "studio.db"
        if db.exists():
            trovati.append(db)
    return trovati


def _peso_in_eccesso(db: Path) -> tuple[int, int, int]:
    """(fascicoli, righe da sgrassare, byte occupati dalla copia in piu')."""
    quanti = 0
    da_sgrassare = 0
    eccesso = 0
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=10) as conn:
        conn.row_factory = sqlite3.Row
        for riga in conn.execute("SELECT id, dati_json FROM fascicoli"):
            quanti += 1
            grezzo = riga["dati_json"] or ""
            if not grezzo:
                continue
            try:
                payload = json.loads(grezzo)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            presenti = [k for k in ("documenti", "attivita", "depositi_pct") if k in payload]
            if not presenti:
                continue
            da_sgrassare += 1
            snello = {k: v for k, v in payload.items() if k not in presenti}
            eccesso += len(grezzo) - len(json.dumps(snello, ensure_ascii=False))
    return quanti, da_sgrassare, eccesso


def _sgrassa(db: Path) -> int:
    """Riscrive solo il campo `dati_json`, senza toccare le colonne fonte."""
    riscritte = 0
    with sqlite3.connect(str(db), timeout=30) as conn:
        conn.row_factory = sqlite3.Row
        righe = list(conn.execute("SELECT id, dati_json FROM fascicoli"))
        for riga in righe:
            grezzo = riga["dati_json"] or ""
            if not grezzo:
                continue
            try:
                payload = json.loads(grezzo)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            snello = {
                k: v for k, v in payload.items()
                if k not in ("documenti", "attivita", "depositi_pct")
            }
            if len(snello) == len(payload):
                continue
            conn.execute(
                "UPDATE fascicoli SET dati_json = ? WHERE id = ?",
                (json.dumps(snello, ensure_ascii=False), riga["id"]),
            )
            riscritte += 1
        conn.commit()
    return riscritte


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="/data", help="Radice dati IUSENTRA.")
    parser.add_argument("--applica", action="store_true", help="Riscrive davvero; senza, e' solo un conteggio.")
    args = parser.parse_args(argv)

    data_root = Path(args.data_root).expanduser()
    archivi = _studio_db_dei_tenant(data_root)
    if not archivi:
        print(f"Nessuno studio.db trovato sotto {data_root}", file=sys.stderr)
        return 1

    totale_eccesso = 0
    for db in archivi:
        quanti, da_sgrassare, eccesso = _peso_in_eccesso(db)
        totale_eccesso += eccesso
        etichetta = db.parent.name
        print(
            f"{etichetta:30s} {quanti:5d} fascicoli, "
            f"{da_sgrassare:5d} da sgrassare, {eccesso/1048576:7.1f} MB in eccesso"
        )
        if args.applica and da_sgrassare:
            riscritte = _sgrassa(db)
            print(f"{'':30s} riscritte {riscritte} righe")

    print(f"\nTotale copia in eccesso: {totale_eccesso/1048576:.1f} MB")
    if not args.applica and totale_eccesso:
        print("Esegui con --applica per riscrivere. Le colonne fonte non vengono toccate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
