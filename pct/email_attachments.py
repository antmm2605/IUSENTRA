"""Utility governate per allegati email e deduplica filesystem."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class DuplicateCandidate:
    sha256: str
    size_bytes: int
    canonical_path: str
    duplicate_path: str


@dataclass
class DeduplicationReport:
    root: str
    dry_run: bool
    files_scanned: int = 0
    duplicate_groups: int = 0
    duplicate_files: int = 0
    bytes_reclaimable: int = 0
    bytes_reclaimed: int = 0
    hardlinked_files: int = 0
    already_hardlinked_files: int = 0
    skipped_files: int = 0
    errors: list[str] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    manifest_path: str | None = None
    duplicates: list[DuplicateCandidate] = field(default_factory=list)

    def to_dict(self, *, include_duplicates: bool = True) -> dict:
        data = asdict(self)
        if not include_duplicates:
            data.pop("duplicates", None)
        return data


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def files_are_same_content(path: str | Path, content: bytes, *, expected_sha256: str | None = None) -> bool:
    file_path = Path(path)
    if not file_path.is_file() or file_path.stat().st_size != len(content):
        return False
    digest = expected_sha256 or content_sha256(content)
    return sha256_file(file_path) == digest


def discover_email_attachment_roots(data_root: str | Path) -> list[Path]:
    root = Path(data_root).resolve()
    if not root.exists() or not root.is_dir():
        return []
    candidates: set[Path] = set()
    top_level = root / "email" / "allegati"
    if top_level.is_dir():
        candidates.add(top_level.resolve())
    tenants = root / "tenants"
    if tenants.is_dir():
        for tenant_email_root in tenants.glob("*/email/allegati"):
            if tenant_email_root.is_dir():
                candidates.add(tenant_email_root.resolve())
    return sorted(candidates, key=lambda item: str(item))


def _iter_files(root: Path, *, min_size_bytes: int) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size >= min_size_bytes:
                yield path
        except OSError:
            continue


def _same_inode(left: Path, right: Path) -> bool:
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _replace_with_hardlink(canonical: Path, duplicate: Path) -> None:
    temp = duplicate.with_name(f".{duplicate.name}.dedup-{uuid.uuid4().hex}.tmp")
    try:
        os.link(canonical, temp)
        os.replace(temp, duplicate)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except OSError:
            pass


def deduplicate_attachment_tree(
    root: str | Path,
    *,
    dry_run: bool = True,
    min_size_bytes: int = 1,
    write_manifest: bool = True,
) -> DeduplicationReport:
    """Trova e opzionalmente deduplica file identici mantenendo invariati i path.

    La deduplica applicata usa hardlink sullo stesso filesystem: non cambia i
    riferimenti salvati nei JSON, ma libera blocchi disco per contenuti identici.
    """

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Directory allegati non trovata: {root_path}")

    report = DeduplicationReport(root=str(root_path), dry_run=dry_run)
    by_size: dict[int, list[Path]] = {}
    for path in _iter_files(root_path, min_size_bytes=max(1, int(min_size_bytes))):
        report.files_scanned += 1
        try:
            by_size.setdefault(path.stat().st_size, []).append(path)
        except OSError as exc:
            report.errors.append(f"{path}: {exc}")

    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        by_hash: dict[str, list[Path]] = {}
        for path in sorted(paths, key=lambda item: str(item)):
            try:
                by_hash.setdefault(sha256_file(path), []).append(path)
            except OSError as exc:
                report.errors.append(f"{path}: {exc}")
        for digest, same_files in by_hash.items():
            if len(same_files) < 2:
                continue
            canonical = same_files[0]
            group_duplicates = same_files[1:]
            report.duplicate_groups += 1
            for duplicate in group_duplicates:
                candidate = DuplicateCandidate(
                    sha256=digest,
                    size_bytes=size,
                    canonical_path=str(canonical),
                    duplicate_path=str(duplicate),
                )
                report.duplicates.append(candidate)
                report.duplicate_files += 1
                if _same_inode(canonical, duplicate):
                    report.already_hardlinked_files += 1
                    continue
                report.bytes_reclaimable += size
                if dry_run:
                    continue
                try:
                    _replace_with_hardlink(canonical, duplicate)
                    if _same_inode(canonical, duplicate):
                        report.hardlinked_files += 1
                        report.bytes_reclaimed += size
                    else:
                        report.skipped_files += 1
                        report.errors.append(f"Hardlink non verificato: {duplicate}")
                except OSError as exc:
                    report.skipped_files += 1
                    report.errors.append(f"{duplicate}: {exc}")

    if write_manifest:
        manifest_dir = root_path.parent / "dedup_reports"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        mode = "dry_run" if dry_run else "apply"
        manifest = manifest_dir / f"email_attachment_dedup_{mode}_{stamp}.json"
        manifest.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        report.manifest_path = str(manifest)
        manifest.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    return report
