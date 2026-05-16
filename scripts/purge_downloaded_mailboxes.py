#!/usr/bin/env python3
"""Svuota posta PEC/ordinaria scaricata preservando configurazioni casella."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


MAILBOX_FILES = ("casella.json", "ordinaria.json")


def human_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TiB"


def _safe_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        try:
            return int(path.stat().st_size)
        except OSError:
            return 0
    total = 0
    for item in path.rglob("*"):
        if not item.is_file() or item.is_symlink():
            continue
        try:
            total += int(item.stat().st_size)
        except OSError:
            continue
    return total


def _safe_file_count(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return 1
    return sum(1 for item in path.rglob("*") if item.is_file() and not item.is_symlink())


def _ensure_inside(root: Path, target: Path) -> None:
    resolved_root = root.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"Percorso fuori dal root dati: {resolved_target}") from exc


def _mail_roots(data_root: Path) -> list[tuple[str, Path]]:
    roots: list[tuple[str, Path]] = []
    global_email = data_root / "email"
    if global_email.exists():
        roots.append(("area condivisa", global_email))
    tenants = data_root / "tenants"
    if tenants.is_dir():
        for tenant_dir in sorted(item for item in tenants.iterdir() if item.is_dir()):
            email_dir = tenant_dir / "email"
            if email_dir.exists():
                roots.append((tenant_dir.name, email_dir))
    return roots


def _purge_mail_root(label: str, email_dir: Path, *, data_root: Path, apply: bool) -> dict[str, Any]:
    _ensure_inside(data_root, email_dir)
    before = _safe_size(email_dir)
    files_before = _safe_file_count(email_dir)
    removed_paths: list[str] = []
    mailbox_files = [email_dir / name for name in MAILBOX_FILES if (email_dir / name).exists()]
    attachment_dir = email_dir / "allegati"
    dedup_reports = email_dir / "dedup_reports"

    if apply:
        email_dir.mkdir(parents=True, exist_ok=True)
        for mailbox in mailbox_files:
            mailbox.write_text("{}\n", encoding="utf-8")
            removed_paths.append(str(mailbox))
        if attachment_dir.exists():
            _ensure_inside(data_root, attachment_dir)
            shutil.rmtree(attachment_dir)
            removed_paths.append(str(attachment_dir))
        attachment_dir.mkdir(parents=True, exist_ok=True)
        if dedup_reports.exists():
            _ensure_inside(data_root, dedup_reports)
            shutil.rmtree(dedup_reports)
            removed_paths.append(str(dedup_reports))
    after = _safe_size(email_dir) if apply else 0
    return {
        "label": label,
        "email_dir": str(email_dir),
        "files_before": files_before,
        "bytes_before": before,
        "bytes_after": after,
        "bytes_reclaimed": max(0, before - after) if apply else before,
        "bytes_before_label": human_bytes(before),
        "bytes_after_label": human_bytes(after),
        "bytes_reclaimed_label": human_bytes(max(0, before - after) if apply else before),
        "removed_paths": removed_paths,
    }


def purge_downloaded_mailboxes(data_root: str | Path, *, apply: bool = False) -> dict[str, Any]:
    root = Path(data_root).resolve()
    reports = [_purge_mail_root(label, email_dir, data_root=root, apply=apply) for label, email_dir in _mail_roots(root)]
    state_files = [root / "fascicoli" / "pec_cancelleria_state.json"]
    tenants = root / "tenants"
    if tenants.is_dir():
        state_files.extend(
            tenant / "fascicoli" / "pec_cancelleria_state.json"
            for tenant in sorted(item for item in tenants.iterdir() if item.is_dir())
        )
    removed_state: list[str] = []
    state_bytes = 0
    if apply:
        for path in state_files:
            if not path.exists() or not path.is_file():
                continue
            _ensure_inside(root, path)
            state_bytes += _safe_size(path)
            path.unlink()
            removed_state.append(str(path))
    else:
        state_bytes = sum(_safe_size(path) for path in state_files if path.exists())

    total_before = sum(int(item["bytes_before"]) for item in reports) + state_bytes
    total_after = sum(int(item["bytes_after"]) for item in reports) if apply else 0
    total_reclaimed = max(0, total_before - total_after) if apply else total_before
    return {
        "applied": apply,
        "data_root": str(root),
        "mail_roots": len(reports),
        "state_files_removed": len(removed_state) if apply else sum(1 for path in state_files if path.exists()),
        "removed_state": removed_state,
        "bytes_before": total_before,
        "bytes_after": total_after,
        "bytes_reclaimed": total_reclaimed,
        "bytes_before_label": human_bytes(total_before),
        "bytes_after_label": human_bytes(total_after),
        "bytes_reclaimed_label": human_bytes(total_reclaimed),
        "reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Svuota PEC/email ordinaria scaricate e allegati, preservando configurazioni casella."
    )
    parser.add_argument("--data-root", default="/data", help="Root dati IUSENTRA.")
    parser.add_argument("--apply", action="store_true", help="Applica la cancellazione. Default: sola analisi.")
    args = parser.parse_args()
    result = purge_downloaded_mailboxes(args.data_root, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
