#!/usr/bin/env python3
"""Backup coerente dei database SQLite tenant prima del deploy Hetzner."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path


GIB = 1024**3
SNAPSHOT_PREFIX = "iusentra-structured-"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_direct_child(path: Path, parent: Path) -> bool:
    return path.parent.resolve() == parent.resolve()


def _backup_sqlite(source: Path, destination: Path) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source.as_posix()}?mode=ro"
    source_connection = sqlite3.connect(source_uri, uri=True, timeout=60)
    destination_connection = sqlite3.connect(destination, timeout=60)
    try:
        source_connection.backup(destination_connection, pages=8192, sleep=0.05)
    finally:
        destination_connection.close()
        source_connection.close()

    verify_uri = f"file:{destination.as_posix()}?mode=ro&immutable=1"
    verify_connection = sqlite3.connect(verify_uri, uri=True, timeout=60)
    try:
        quick_check = str(verify_connection.execute("PRAGMA quick_check(1)").fetchone()[0])
    finally:
        verify_connection.close()
    if quick_check.lower() != "ok":
        raise RuntimeError(f"Quick check fallito per {source}: {quick_check}")

    return {
        "source": str(source),
        "destination": str(destination.name),
        "source_bytes": source.stat().st_size,
        "backup_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "quick_check": quick_check,
    }


def create_structured_backup(
    *,
    source_root: Path,
    backup_dir: Path,
    retention_count: int = 1,
    min_free_gib: int = 2,
    prune_legacy_single_db: bool = False,
) -> dict[str, object]:
    source_root = source_root.resolve(strict=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_dir.resolve(strict=True)
    sources = sorted(
        path.resolve(strict=True)
        for path in source_root.glob("*/studio.db")
        if path.is_file() and not path.is_symlink()
    )
    if not sources:
        raise RuntimeError(f"Nessun database tenant studio.db trovato sotto {source_root}")
    for source in sources:
        if source.parent.parent != source_root:
            raise RuntimeError(f"Database fuori dal perimetro tenant: {source}")

    source_bytes = sum(path.stat().st_size for path in sources)
    free_bytes = shutil.disk_usage(backup_dir).free
    required_bytes = source_bytes + max(0, min_free_gib) * GIB
    if free_bytes < required_bytes:
        raise RuntimeError(
            "Spazio insufficiente per il backup SQLite strutturato: "
            f"libero={free_bytes}, richiesto={required_bytes}."
        )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    staging = Path(tempfile.mkdtemp(prefix=f".{SNAPSHOT_PREFIX}", dir=backup_dir))
    final_dir = backup_dir / f"{SNAPSHOT_PREFIX}{stamp}"
    completed = False
    try:
        entries: list[dict[str, object]] = []
        for source in sources:
            tenant_id = source.parent.name
            destination = staging / tenant_id / "studio.db"
            entry = _backup_sqlite(source, destination)
            entry["tenant_id"] = tenant_id
            entries.append(entry)

        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_of_truth": "sqlite",
            "scope": "tenant_studio_databases",
            "database_count": len(entries),
            "source_bytes": source_bytes,
            "backup_bytes": sum(int(entry["backup_bytes"]) for entry in entries),
            "retention_count": max(1, retention_count),
            "entries": entries,
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        staging.rename(final_dir)
        completed = True

        snapshots = sorted(
            (
                path
                for path in backup_dir.glob(f"{SNAPSHOT_PREFIX}*")
                if path.is_dir() and _is_direct_child(path, backup_dir)
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old_snapshot in snapshots[max(1, retention_count) :]:
            shutil.rmtree(old_snapshot)

        if prune_legacy_single_db:
            for pattern in (
                "studio-legale-*-studio-*.db",
                "studio-legale-*-studio-*.db.sha256",
                "studio-legale-*-studio-*.db-wal",
                "studio-legale-*-studio-*.db-shm",
            ):
                for legacy_path in backup_dir.glob(pattern):
                    if legacy_path.is_file() and _is_direct_child(legacy_path, backup_dir):
                        legacy_path.unlink()

        return {
            "ok": True,
            "snapshot": str(final_dir),
            "source_of_truth": "sqlite",
            "database_count": len(entries),
            "source_bytes": source_bytes,
            "backup_bytes": sum(int(entry["backup_bytes"]) for entry in entries),
            "retention_count": max(1, retention_count),
        }
    finally:
        if not completed and staging.exists() and _is_direct_child(staging, backup_dir):
            shutil.rmtree(staging)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--retention-count", type=int, default=1)
    parser.add_argument("--min-free-gib", type=int, default=2)
    parser.add_argument("--prune-legacy-single-db", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    result = create_structured_backup(
        source_root=args.source_root,
        backup_dir=args.backup_dir,
        retention_count=args.retention_count,
        min_free_gib=args.min_free_gib,
        prune_legacy_single_db=args.prune_legacy_single_db,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
