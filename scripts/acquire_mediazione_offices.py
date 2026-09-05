"""Bounded, resumable import of all public ministry offices, with exact totals."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pct.mediazione_directory_repository import MediazioneDirectoryRepository
from pct.mediazione_official_offices import acquire_offices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--number", default="")
    parser.add_argument("--registry-json", type=Path,
                        help="Importazione esplicita dello snapshot ministeriale prima dell'acquisizione.")
    args = parser.parse_args()
    repo = MediazioneDirectoryRepository(args.db, postgres_dsn=os.environ.get("MEDIAZIONE_DATABASE_URL", ""))
    if args.registry_json:
        snapshot = json.loads(args.registry_json.read_text(encoding="utf-8"))
        if "tables" in snapshot:
            snapshot = snapshot["tables"]["organismi_mediazione_elenco"]
        metadata = snapshot.get("metadata") or snapshot
        checked_at = (metadata.get("last_successful_sync") or metadata.get("last_synced_at")
                      or metadata.get("last_sync_at") or metadata.get("updated_at"))
        if not checked_at:
            parser.error("Il registro non dichiara la data di acquisizione.")
        repo.import_registry(snapshot["rows"],
                             source="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
                             checked_at=checked_at)
    existing = repo.office_snapshots()
    rows = [r for r in repo.records() if str(r["registration_number"]) not in existing]
    if args.number:
        rows = [r for r in repo.records(active_only=False) if str(r["registration_number"]) == args.number]
        if not rows:
            parser.error("Organismo non presente nel registro acquisito.")
    rows = rows[:max(1, min(100, args.limit))]
    deadline = time.monotonic() + 230
    failed = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending = {pool.submit(acquire_offices, str(r["registration_number"]), deadline=deadline): str(r["registration_number"]) for r in rows}
        for i, future in enumerate(as_completed(pending), 1):
            number = pending[future]
            try:
                snapshot = future.result()
                repo.save_offices(number, snapshot)
                print(json.dumps({"number": number, "offices": snapshot["expected_count"], "pages": snapshot["pages"]}), flush=True)
            except Exception as exc:
                failed.append({"number": number, "error": str(exc)})
    print(json.dumps({"source_of_truth": repo.source_of_truth, "processed": len(rows), "failures": failed,
                      "acquired_organisms": len(repo.office_snapshots())}, ensure_ascii=False), flush=True)
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
