#!/usr/bin/env python3
"""Backup coerente dei database SQLite tenant prima del deploy Hetzner."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
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


@contextmanager
def _maintenance_lock(backup_dir: Path):
    with (backup_dir / ".iusentra-backup-maintenance.lock").open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            lock, unlock = (
                lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1),
                lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1),
            )
        else:
            import fcntl

            lock, unlock = (
                lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB),
                lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN),
            )
        try:
            lock()
        except OSError as exc:
            raise RuntimeError("Manutenzione backup già in corso: nessuna retention eseguita.") from exc
        try:
            yield
        finally:
            unlock()


def _technical_evidence(snapshots: list[Path]) -> list[Path]:
    files = []
    for snapshot in snapshots:
        root = snapshot / "supplemental-technical"
        if root.is_symlink():
            raise RuntimeError("Archivio tecnico collegato fuori dal backup: retention sospesa.")
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or not path.resolve().is_relative_to(snapshot.resolve()):
                raise RuntimeError("Fonte tecnica fuori dal backup: retention sospesa.")
            if path.is_file():
                files.append(path)
    return files


def _copy_technical_file(source: Path, destination: Path) -> None:
    shutil.copyfile(source, destination)
    with destination.open("r+b") as handle:
        handle.flush()
        os.fsync(handle.fileno())
    shutil.copystat(source, destination)


def _write_manifest(path: Path, value: dict[str, object]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _preserve_technical_evidence(files: list[Path], staging: Path) -> dict[str, object] | None:
    if not files:
        return None
    root = staging / "supplemental-technical"
    entries = []
    stored = set()
    total = 0
    for source in files:
        before = source.stat()
        digest = _sha256(source)
        destination = root / "objects" / digest / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination not in stored:
            _copy_technical_file(source, destination)
            if destination.stat().st_size != before.st_size or _sha256(destination) != digest:
                raise RuntimeError("Copia tecnica non verificata: il backup precedente resta conservato.")
            _sync_directory(destination.parent)
            stored.add(destination)
            total += before.st_size
        after = source.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise RuntimeError("Fonte tecnica cambiata durante la copia: retention sospesa.")
        entries.append(
            {
                "source": str(source),
                "stored": str(destination.relative_to(staging)),
                "bytes": before.st_size,
                "sha256": digest,
            }
        )
    _sync_directory(root / "objects")
    index = root / "preservation-index.json"
    _write_manifest(index, {"schema_version": 1, "files": entries})
    _sync_directory(root)
    return {
        "index": str(index.relative_to(staging)),
        "index_sha256": _sha256(index),
        "files": len(stored),
        "bytes": total,
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
    with _maintenance_lock(backup_dir):
        return _create_structured_backup(
            source_root=source_root,
            backup_dir=backup_dir,
            retention_count=retention_count,
            min_free_gib=min_free_gib,
            prune_legacy_single_db=prune_legacy_single_db,
        )


def _create_structured_backup(
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

    previous = [
        path
        for path in backup_dir.glob(f"{SNAPSHOT_PREFIX}*")
        if path.is_dir() and not path.is_symlink() and _is_direct_child(path, backup_dir)
    ]
    technical = _technical_evidence(previous)

    def signatures():
        return {
            str(path): (path.stat().st_size, path.stat().st_mtime_ns, path.stat().st_ino)
            for path in _technical_evidence(previous)
        }

    initial_technical = signatures()
    technical_bytes = sum(path.stat().st_size for path in technical)
    source_bytes = sum(path.stat().st_size for path in sources)
    free_bytes = shutil.disk_usage(backup_dir).free
    required_bytes = source_bytes + technical_bytes + max(0, min_free_gib) * GIB
    if free_bytes < required_bytes:
        raise RuntimeError(
            f"Spazio insufficiente per il backup SQLite strutturato: libero={free_bytes}, richiesto={required_bytes}."
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

        supplemental = _preserve_technical_evidence(technical, staging)
        if signatures() != initial_technical:
            raise RuntimeError("Contenuti tecnici cambiati durante il backup: copie precedenti conservate.")
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
        if supplemental is not None:
            manifest["supplemental_technical"] = supplemental
        _write_manifest(staging / "manifest.json", manifest)
        _sync_directory(staging)
        staging.rename(final_dir)
        _sync_directory(backup_dir)
        completed = True

        snapshots = sorted(
            (
                path
                for path in backup_dir.glob(f"{SNAPSHOT_PREFIX}*")
                if path.is_dir() and not path.is_symlink() and path != final_dir and _is_direct_child(path, backup_dir)
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if signatures() != initial_technical:
            raise RuntimeError("Contenuti tecnici cambiati: retention sospesa, copie conservate.")
        for old_snapshot in snapshots[max(1, retention_count) - 1 :]:
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
