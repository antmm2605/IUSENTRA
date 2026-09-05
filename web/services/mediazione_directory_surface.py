"""Public-directory reads only. No tenant case data or network calls."""
from pathlib import Path
import os
from pct.mediazione_directory_repository import MediazioneDirectoryRepository


def directory(config):
    anchor = config.get("NORMATIVE_TABLES_DB")
    path = config.get("MEDIAZIONE_DIRECTORY_DB")
    if not path and anchor:
        path = Path(anchor).with_name("mediazione_directory.db")
    if not path:
        return None
    # Public registry: never infer the database from the authenticated tenant.
    dsn = str(config.get("MEDIAZIONE_DATABASE_URL") or os.environ.get("MEDIAZIONE_DATABASE_URL") or "").strip()
    if not dsn and not Path(path).is_file():
        return None
    return MediazioneDirectoryRepository(path, postgres_dsn=dsn)


def enrich_locations(records, config):
    repo = directory(config)
    snapshots = repo.office_snapshots() if repo else {}
    for record in records:
        snapshot = snapshots.get(record["registryNumber"]) if record["registryKind"] == "organismo" else None
        record["locations"] = []
        record["officeCount"] = None
        if snapshot:
            unique = {(o["region"], o["province"], o["city"]) for o in snapshot["offices"]}
            record["locations"] = [dict(region=r, province=p, city=c) for r, p, c in sorted(unique)]
            record["officeCount"] = snapshot["expected_count"]
    return records


def office_detail(number, config):
    repo = directory(config)
    snapshot = repo.office_snapshots(number).get(number) if repo else None
    return {"ok": True, "available": snapshot is not None, **(snapshot or {})}
