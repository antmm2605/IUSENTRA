#!/usr/bin/env python3
"""Compatta storage runtime IUSENTRA senza cambiare i path applicativi."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.email_attachments import deduplicate_attachment_tree, discover_email_attachment_roots  # noqa: E402


def discover_backup_roots(data_root: str | Path) -> list[Path]:
    root = Path(data_root).resolve()
    if not root.exists() or not root.is_dir():
        return []
    candidates: set[Path] = set()
    top_level = root / "backup"
    if top_level.is_dir():
        candidates.add(top_level.resolve())
    tenants = root / "tenants"
    if tenants.is_dir():
        for tenant_backup_root in tenants.glob("*/backup"):
            if tenant_backup_root.is_dir():
                candidates.add(tenant_backup_root.resolve())
    return sorted(candidates, key=lambda item: str(item))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deduplica con hardlink allegati email e backup mirror nello storage dati."
    )
    parser.add_argument("--data-root", default="/data", help="Root dati applicativa.")
    parser.add_argument("--apply", action="store_true", help="Applica la deduplica. Default: dry-run.")
    parser.add_argument("--min-size-bytes", type=int, default=4096, help="Ignora file piu' piccoli della soglia.")
    parser.add_argument("--no-email", action="store_true", help="Esclude email/allegati.")
    parser.add_argument("--no-backups", action="store_true", help="Esclude backup e mirror tenant.")
    parser.add_argument("--write-manifest", action="store_true", help="Scrive manifest dettagliati per root.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    roots: list[Path] = []
    if not args.no_email:
        roots.extend(discover_email_attachment_roots(args.data_root))
    if not args.no_backups:
        roots.extend(discover_backup_roots(args.data_root))

    seen: set[Path] = set()
    unique_roots: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            unique_roots.append(resolved)
            seen.add(resolved)

    reports = [
        deduplicate_attachment_tree(
            root,
            dry_run=not args.apply,
            min_size_bytes=args.min_size_bytes,
            write_manifest=args.write_manifest,
        ).to_dict(include_duplicates=False)
        for root in unique_roots
    ]
    payload = {
        "dry_run": not args.apply,
        "roots": [str(root) for root in unique_roots],
        "roots_scanned": len(unique_roots),
        "files_scanned": sum(int(report["files_scanned"]) for report in reports),
        "duplicate_files": sum(int(report["duplicate_files"]) for report in reports),
        "physical_duplicate_files": sum(int(report.get("physical_duplicate_files", 0)) for report in reports),
        "already_hardlinked_files": sum(int(report["already_hardlinked_files"]) for report in reports),
        "hardlinked_files": sum(int(report["hardlinked_files"]) for report in reports),
        "bytes_reclaimable": sum(int(report["bytes_reclaimable"]) for report in reports),
        "bytes_reclaimed": sum(int(report["bytes_reclaimed"]) for report in reports),
        "reports": reports,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if any(report.get("errors") for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
