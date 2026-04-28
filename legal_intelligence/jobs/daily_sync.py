"""Comando giornaliero per il controllo delle fonti ufficiali.

Esecuzione prevista in produzione:
    python -m legal_intelligence.jobs.daily_sync
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from legal_intelligence.engine import FetchCallable, LegalIntelligenceDailyEngine
from legal_intelligence.sources import DEFAULT_LEGAL_SOURCES


def _default_db_path() -> Path:
    return Path(os.getenv("LEGAL_INTELLIGENCE_DAILY_DB") or "data/legal_intelligence/daily.sqlite")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Esegue il controllo giornaliero delle fonti ufficiali.")
    parser.add_argument("--db", default=str(_default_db_path()), help="Percorso SQLite del motore giornaliero.")
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help="ID fonte da controllare. Ripetibile; se omesso controlla tutte le fonti abilitate.",
    )
    parser.add_argument("--list", action="store_true", help="Mostra le fonti configurate e termina.")
    parser.add_argument("--json", action="store_true", help="Stampa il riepilogo in JSON.")
    return parser


def _print_sources() -> None:
    for source in DEFAULT_LEGAL_SOURCES:
        status = "abilitata" if source.enabled else "disabilitata"
        print(f"{source.id}\t{status}\t{source.apply_mode}\t{source.name}")


def main(argv: Sequence[str] | None = None, *, fetcher: FetchCallable | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.list:
        _print_sources()
        return 0
    engine = LegalIntelligenceDailyEngine(args.db, fetcher=fetcher)
    summary = engine.run_daily_sync(source_ids=list(args.source or []))
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            "Controllo Legal Intelligence completato: "
            f"{summary.get('sources_checked', 0)} fonti, "
            f"{summary.get('updates_detected', 0)} variazioni, "
            f"{summary.get('updates_applied', 0)} applicate, "
            f"{summary.get('pending_review', 0)} in revisione, "
            f"{summary.get('errors_count', 0)} errori."
        )
    return 0 if summary.get("status") in {"completed", "completed_with_errors"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
