"""Explicit resumable public-directory job. Does not send any study/case data."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pct.mediazione_directory_repository import MediazioneDirectoryRepository
from pct.mediazione_public_sources import inspect_organism


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--registry-json", type=Path)
    parser.add_argument("--registry-from-hetzner", action="store_true")
    parser.add_argument("--check-sites", action="store_true")
    parser.add_argument("--retry", action="store_true")
    parser.add_argument("--workers", type=int, default=4, choices=range(1, 7))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--organismo", help="Numero di registro per una verifica mirata.")
    args = parser.parse_args()
    repo = MediazioneDirectoryRepository(args.db, postgres_dsn=os.environ.get("MEDIAZIONE_DATABASE_URL", ""))
    if args.registry_json and args.registry_from_hetzner:
        parser.error("Scegli una sola fonte di importazione.")
    if args.registry_from_hetzner:
        # Only the public current organism rows. No tenants, history or individual trainers.
        script = ('import json;d=json.load(open("/opt/iusentra/data/intelligence/tabelle_normative.json"));'
                  't=d["tables"]["organismi_mediazione_elenco"];'
                  'print(json.dumps({"rows":[r for r in t["rows"] if r.get("registry_kind")=="organismo"],'
                  '"metadata":{k:v for k,v in t.items() if k not in ("rows","versions")}},ensure_ascii=False))')
        raw = subprocess.run(["ssh", "iusentra-hetzner", "python3 -c '" + script + "'"],
                             capture_output=True, check=True, timeout=60)
        snapshot = json.loads(raw.stdout)
    elif args.registry_json:
        snapshot = json.loads(args.registry_json.read_text(encoding="utf-8"))
        if "tables" in snapshot:
            snapshot = snapshot["tables"]["organismi_mediazione_elenco"]
    else:
        snapshot = None
    if snapshot:
        metadata = snapshot.get("metadata") or snapshot
        checked_at = (metadata.get("last_successful_sync") or metadata.get("last_synced_at")
                      or metadata.get("last_sync_at") or metadata.get("updated_at"))
        if not checked_at:
            raise ValueError("Il registro non dichiara la data di acquisizione: importazione interrotta.")
        count = repo.import_registry(snapshot["rows"],
            source="https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX", checked_at=checked_at)
        print(json.dumps({"imported": count, "registry_checked_at": checked_at}), flush=True)
    if args.check_sites:
        rows = [r for r in repo.records() if args.retry or not r["directory_check"]]
        if args.organismo:
            rows = [r for r in rows if str(r["registration_number"]) == args.organismo]
        if args.limit:
            rows = rows[:args.limit]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(inspect_organism, row): row["registration_number"] for row in rows}
            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                repo.save_check(str(futures[future]), result)
                if i % 20 == 0 or i == len(futures):
                    print(json.dumps({"processed": i, "scheduled": len(futures), **repo.summary()}), flush=True)
    print(json.dumps(repo.summary(), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
