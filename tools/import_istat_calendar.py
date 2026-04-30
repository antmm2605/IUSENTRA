"""Import festivita ufficiali per il calcolatore termini processuali.

Il file atteso e' un CSV con colonne almeno `date` e `description`
(`type` opzionale). Il checksum SHA-256 e' opzionale ma consigliato in
produzione per tracciare la fonte usata dal motore di calcolo.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from pct.termini_processuali import DeadlinePracticeRepository, holidays_from_csv


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa un CSV festivita nel repository termini processuali.")
    parser.add_argument("csv", help="Percorso CSV con colonne date, description, type opzionale")
    parser.add_argument("--db", default="data/scadenziario/termini_processuali.json", help="Repository JSON o SQLite")
    parser.add_argument("--backend", choices=["json", "sqlite"], default="json")
    parser.add_argument("--year", type=int, required=True, help="Anno fonte del calendario")
    parser.add_argument("--source", default="CSV ufficiale")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--calendar-version", default="")
    parser.add_argument("--sha256", default="", help="Checksum atteso del CSV")
    parser.add_argument("--notes", default="")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    actual_checksum = _sha256(csv_path)
    if args.sha256 and args.sha256.lower() != actual_checksum.lower():
        raise SystemExit(f"Checksum non valido: atteso {args.sha256}, trovato {actual_checksum}")

    repo = (
        DeadlinePracticeRepository.sqlite(args.db)
        if args.backend == "sqlite"
        else DeadlinePracticeRepository.json(args.db)
    )
    summary = repo.import_holidays(
        holidays_from_csv(csv_path),
        source_year=args.year,
        source=args.source,
        source_url=args.source_url,
        checksum_sha256=actual_checksum,
        calendar_version=args.calendar_version or None,
        notes=args.notes,
    )
    print(
        "Calendario importato: "
        f"{summary['imported']} festivita, versione {summary['calendarVersion']}, "
        f"sha256 {summary['checksumSha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
