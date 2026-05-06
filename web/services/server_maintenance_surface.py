"""Superficie Superadmin per server, storage e manutenzione prestazionale."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
from typing import Any

from flask import current_app

from pct.email_attachments import deduplicate_attachment_tree, discover_email_attachment_roots
from scripts.compact_iusentra_storage import discover_backup_roots


@dataclass(frozen=True)
class StorageArea:
    code: str
    label: str
    path: str
    exists: bool
    size_bytes: int
    size_label: str
    note: str


def human_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TiB"


def _sum_report_int(reports: list[dict[str, Any]], key: str) -> int:
    return sum(int(report.get(key, 0) or 0) for report in reports)


def directory_size(path: str | Path, *, seen_inodes: set[tuple[int, int]] | None = None) -> int:
    """Stima la dimensione senza contare due volte hardlink nello stesso ambito."""

    root = Path(path)
    seen = seen_inodes if seen_inodes is not None else set()
    if not root.exists():
        return 0
    if root.is_file():
        try:
            stat = root.stat()
            inode_key = (stat.st_dev, stat.st_ino)
            if inode_key in seen:
                return 0
            seen.add(inode_key)
            return int(stat.st_size)
        except OSError:
            return 0
    total = 0
    for current_root, _, files in os.walk(root):
        for filename in files:
            try:
                file_path = Path(current_root) / filename
                stat = file_path.stat()
                inode_key = (stat.st_dev, stat.st_ino)
                if inode_key in seen:
                    continue
                seen.add(inode_key)
                total += int(stat.st_size)
            except OSError:
                continue
    return total


def directory_size_many(paths: list[Path]) -> int:
    seen: set[tuple[int, int]] = set()
    return sum(directory_size(path, seen_inodes=seen) for path in paths)


def resolve_data_root(config: dict[str, Any] | None = None) -> Path:
    cfg = config or current_app.config
    candidates = [
        os.getenv("IUSENTRA_DATA_DIR"),
        cfg.get("IUSENTRA_DATA_DIR"),
        str(Path(str(cfg.get("AUTH_DB", ""))).parent.parent) if cfg.get("AUTH_DB") else "",
        "/data",
        "./data",
    ]
    for candidate in candidates:
        if candidate and Path(str(candidate)).exists():
            return Path(str(candidate)).resolve()
    return Path("./data").resolve()


def resolve_external_backup_dir(config: dict[str, Any] | None = None) -> Path:
    cfg = config or current_app.config
    return Path(
        str(
            os.getenv("IUSENTRA_BACKUP_DIR")
            or cfg.get("IUSENTRA_BACKUP_DIR")
            or "/opt/iusentra/backups"
        )
    )


def _area(code: str, label: str, path: Path, note: str = "") -> StorageArea:
    exists = path.exists()
    size = directory_size(path) if exists else 0
    return StorageArea(
        code=code,
        label=label,
        path=str(path),
        exists=exists,
        size_bytes=size,
        size_label=human_bytes(size),
        note=note,
    )


def _tenant_rows(data_root: Path) -> list[dict[str, Any]]:
    tenants_root = data_root / "tenants"
    if not tenants_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for tenant_dir in sorted([item for item in tenants_root.iterdir() if item.is_dir()], key=lambda item: item.name):
        email_dir = tenant_dir / "email" / "allegati"
        backup_dir = tenant_dir / "backup"
        db_files = list(tenant_dir.glob("*.db")) + list((tenant_dir / "sql").glob("*.db"))
        db_size = sum(directory_size(path) for path in db_files)
        email_size = directory_size(email_dir)
        backup_size = directory_size(backup_dir)
        total_size = directory_size(tenant_dir)
        recommendations = []
        if backup_size > 256 * 1024**2:
            recommendations.append(
                "Backup mirror sopra 256 MiB: verificare retention; compattare solo se l'analisi segnala file da compattare."
            )
        if email_size > 256 * 1024**2:
            recommendations.append("Verificare deduplica allegati email.")
        if db_size > 128 * 1024**2:
            recommendations.append("Valutare VACUUM SQLite in finestra di manutenzione.")
        if not recommendations:
            recommendations.append("Nessuna manutenzione urgente rilevata.")
        rows.append(
            {
                "slug": tenant_dir.name,
                "path": str(tenant_dir),
                "total_bytes": total_size,
                "total_label": human_bytes(total_size),
                "email_bytes": email_size,
                "email_label": human_bytes(email_size),
                "backup_bytes": backup_size,
                "backup_label": human_bytes(backup_size),
                "database_bytes": db_size,
                "database_label": human_bytes(db_size),
                "recommendations": recommendations,
            }
        )
    return sorted(rows, key=lambda row: int(row["total_bytes"]), reverse=True)


def build_server_maintenance_surface(config: dict[str, Any] | None = None) -> dict[str, Any]:
    data_root = resolve_data_root(config)
    backup_dir = resolve_external_backup_dir(config)
    disk = shutil.disk_usage(data_root if data_root.exists() else Path("/"))
    email_roots = discover_email_attachment_roots(data_root)
    backup_roots = discover_backup_roots(data_root)
    email_size = directory_size_many(email_roots)
    backup_mirror_size = directory_size_many(backup_roots)
    backup_external_size = directory_size(backup_dir) if backup_dir.exists() else 0
    retention_max_gib = int(str(os.getenv("IUSENTRA_BACKUP_RETENTION_MAX_GIB") or "24").strip() or 24)

    areas = [
        _area("data", "Dati applicativi", data_root, "Root runtime tenant-aware."),
        _area("tenants", "Tenant", data_root / "tenants", "Studi, database e documenti separati per tenant."),
        _area("email", "Allegati email", data_root / "email" / "allegati", "Allegati globali deduplicabili."),
        _area("tenant_email", "Allegati email tenant", data_root / "tenants", "Somma inclusa nei tenant."),
        _area("backup_mirror", "Backup interni e mirror", data_root / "backup", "Backup applicativi nello storage live."),
        _area("ollama", "Modelli AI locali", data_root / "ollama", "Modelli Lex/Ollama locali."),
        _area("import", "Import portali", data_root / "portale", "Staging import autorizzati."),
        _area("redis", "Redis persistente", data_root / "redis", "Append-only file e snapshot Redis."),
    ]
    recommendations = []
    used_ratio = disk.used / disk.total if disk.total else 0
    if used_ratio >= 0.8:
        recommendations.append("Disco oltre l'80%: eseguire backup, compattazione e pulizia cache Docker.")
    if backup_external_size > retention_max_gib * 1024**3:
        recommendations.append("Backup esterni oltre il tetto configurato: applicare retention e compressione alta.")
    if backup_mirror_size > 512 * 1024**2:
        recommendations.append(
            "Backup mirror interni sopra 512 MiB: verificare retention; la compattazione e' utile solo se l'analisi segnala file da compattare."
        )
    if not recommendations:
        recommendations.append("Nessuna azione urgente: mantenere backup e compattazione nel ciclo di manutenzione.")

    return {
        "mock_fallback": False,
        "data_root": str(data_root),
        "backup_dir": str(backup_dir),
        "disk": {
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "used_percent": round(used_ratio * 100, 1),
            "total_label": human_bytes(disk.total),
            "used_label": human_bytes(disk.used),
            "free_label": human_bytes(disk.free),
        },
        "summary": {
            "email_roots": len(email_roots),
            "backup_roots": len(backup_roots),
            "email_size_label": human_bytes(email_size),
            "backup_mirror_size_label": human_bytes(backup_mirror_size),
            "backup_external_size_label": human_bytes(backup_external_size),
        },
        "tenants": _tenant_rows(data_root),
        "areas": [area.__dict__ for area in sorted(areas, key=lambda item: item.size_bytes, reverse=True)],
        "actions": {
            "analyze_compaction": "/admin/server-manutenzione/analizza-compattazione",
            "apply_compaction": "/admin/server-manutenzione/compatta",
        },
        "recommendations": recommendations,
    }


def run_storage_compaction(
    *,
    apply: bool = False,
    data_root: str | Path | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    root = Path(data_root) if data_root else resolve_data_root()
    slug = str(tenant_slug or "").strip()
    if slug:
        tenant_root = root / "tenants" / slug
        roots = [
            tenant_root / "email" / "allegati",
            tenant_root / "backup",
        ]
        roots = [path for path in roots if path.is_dir()]
    else:
        roots = [*discover_email_attachment_roots(root), *discover_backup_roots(root)]
    seen: set[Path] = set()
    reports = []
    for candidate in roots:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        reports.append(
            deduplicate_attachment_tree(
                resolved,
                dry_run=not apply,
                min_size_bytes=4096,
                write_manifest=False,
            ).to_dict(include_duplicates=False)
        )
    physical_duplicates = _sum_report_int(reports, "physical_duplicate_files")
    already_hardlinked = _sum_report_int(reports, "already_hardlinked_files")
    hardlinked_now = _sum_report_int(reports, "hardlinked_files")
    bytes_reclaimable = _sum_report_int(reports, "bytes_reclaimable")
    bytes_reclaimed = _sum_report_int(reports, "bytes_reclaimed")
    return {
        "mock_fallback": False,
        "applied": apply,
        "tenant_slug": slug,
        "roots_scanned": len(reports),
        "files_scanned": _sum_report_int(reports, "files_scanned"),
        "duplicate_files": _sum_report_int(reports, "duplicate_files"),
        "physical_duplicate_files": physical_duplicates,
        "already_hardlinked_files": already_hardlinked,
        "hardlinked_files": hardlinked_now,
        "bytes_reclaimable": bytes_reclaimable,
        "bytes_reclaimed": bytes_reclaimed,
        "bytes_reclaimable_label": human_bytes(bytes_reclaimable),
        "bytes_reclaimed_label": human_bytes(bytes_reclaimed),
        "reports": reports,
    }
