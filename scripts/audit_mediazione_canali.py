"""Resumable bounded research of ALL active organisms. Never sends legal data."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pct.mediazione_channel_research import RESEARCH_VERSION, inspect_channels
from pct.mediazione_directory_repository import MediazioneDirectoryRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, choices=range(1, 7), default=6)
    parser.add_argument("--number")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--export", type=Path)
    parser.add_argument("--alternatives", type=Path, help="Verified public source URLs keyed by registry number")
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error("Use resumable batches of at most 20 organisms.")
    repo = MediazioneDirectoryRepository(args.db, postgres_dsn=os.environ.get("MEDIAZIONE_DATABASE_URL", ""))
    all_rows, checks = repo.records(), repo.channel_checks()
    alternatives = json.loads(args.alternatives.read_text(encoding="utf-8")) if args.alternatives else {}
    rows = [r for r in all_rows if (not args.number or str(r["registration_number"]) == args.number)
            and (args.retry or checks.get(str(r["registration_number"]), {}).get("research_version") != RESEARCH_VERSION)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(inspect_channels, r, alternatives=alternatives.get(str(r["registration_number"]), [])): r for r in rows[:args.limit]}
        for future in as_completed(futures):
            row = futures[future]
            result = future.result()
            repo.save_channel_check(str(row["registration_number"]), result)
            print(json.dumps({"number": row["registration_number"], "name": row["name"], "status": result["status"],
                              "pages": len(result["pages"]), "contacts": len(result["contacts"]), "api_documents": len(result["api_documents"])}, ensure_ascii=False), flush=True)
    checks = repo.channel_checks()
    current = [checks[str(r["registration_number"])] for r in all_rows if str(r["registration_number"]) in checks]
    summary = {"source_of_truth": repo.source_of_truth, "active": len(all_rows), "researched": len(current),
               "pending": len(all_rows) - len(current), "statuses": dict(Counter(r["status"] for r in current)),
               "ready_for_submission": 0}
    if args.export:
        args.export.parent.mkdir(parents=True, exist_ok=True)
        with args.export.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["Numero registro", "Organismo", "Sito da registro", "Stato ricerca", "Pagine lette", "PEC rilevate da revisionare", "Documentazione API da verificare", "Fonti", "Problemi"])
            for row in all_rows:
                result = checks.get(str(row["registration_number"]), {})
                writer.writerow([row["registration_number"], row["name"], row["website"], result.get("status", "da_ricercare"),
                                 len(result.get("pages", [])), "; ".join(sorted({c["address"] for c in result.get("contacts", []) if c["pec_explicit"]})),
                                 "; ".join(a["url"] for a in result.get("api_documents", [])),
                                 "; ".join(p["url"] for p in result.get("pages", [])),
                                 "; ".join(e["error"] for e in result.get("errors", []))])
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
