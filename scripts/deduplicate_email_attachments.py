#!/usr/bin/env python
"""Analizza o deduplica allegati email IUSENTRA tramite hardlink sicuri."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pct.email_attachments import deduplicate_attachment_tree, discover_email_attachment_roots  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deduplica gli allegati email tenant-aware mantenendo invariati i path salvati.",
    )
    parser.add_argument(
        "roots",
        nargs="*",
        help="Directory allegati da processare. Esempio: /data/tenants/<tenant>/email/allegati",
    )
    parser.add_argument(
        "--data-root",
        default="",
        help="Root dati da cui scoprire automaticamente email/allegati e tenants/*/email/allegati.",
    )
    parser.add_argument("--apply", action="store_true", help="Applica la deduplica. Senza questo flag esegue solo dry-run.")
    parser.add_argument("--min-size-bytes", type=int, default=1, help="Dimensione minima dei file da considerare.")
    parser.add_argument(
        "--no-manifest",
        action="store_true",
        help="Non scrivere il report JSON accanto alla directory email.",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    roots = [Path(value) for value in args.roots]
    if args.data_root:
        roots.extend(discover_email_attachment_roots(args.data_root))

    unique_roots = sorted({path.resolve() for path in roots}, key=lambda item: str(item))
    if not unique_roots:
        raise SystemExit("Nessuna directory allegati indicata o scoperta.")

    reports = [
        deduplicate_attachment_tree(
            root,
            dry_run=not args.apply,
            min_size_bytes=args.min_size_bytes,
            write_manifest=not args.no_manifest,
        ).to_dict()
        for root in unique_roots
    ]

    summary = {
        "ok": True,
        "dry_run": not args.apply,
        "roots": len(reports),
        "files_scanned": sum(int(report["files_scanned"]) for report in reports),
        "duplicate_files": sum(int(report["duplicate_files"]) for report in reports),
        "bytes_reclaimable": sum(int(report["bytes_reclaimable"]) for report in reports),
        "bytes_reclaimed": sum(int(report["bytes_reclaimed"]) for report in reports),
        "hardlinked_files": sum(int(report["hardlinked_files"]) for report in reports),
        "skipped_files": sum(int(report["skipped_files"]) for report in reports),
        "reports": reports,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
