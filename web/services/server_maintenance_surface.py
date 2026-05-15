"""Superficie Superadmin per server, storage e manutenzione prestazionale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import os
import shutil
import time
from typing import Any

from flask import current_app, has_app_context

from pct.email_attachments import deduplicate_attachment_tree, discover_email_attachment_roots
from scripts.compact_iusentra_storage import discover_backup_roots

DEFAULT_BACKUP_RETENTION_DAYS = 14
DEFAULT_BACKUP_RETENTION_COUNT = 3
DEFAULT_BACKUP_RETENTION_MIN_COUNT = 2
DEFAULT_BACKUP_RETENTION_MAX_GIB = 8
DEFAULT_TENANT_STORAGE_SCAN_MAX_FILES = 12_000
DEFAULT_TENANT_STORAGE_SCAN_SECONDS = 0.9
DEFAULT_GLOBAL_STORAGE_SCAN_MAX_FILES = 6_000
DEFAULT_GLOBAL_STORAGE_SCAN_SECONDS = 0.45
BACKUP_ARCHIVE_SUFFIXES = (".tar.zst", ".tar.gz")


@dataclass(frozen=True)
class StorageArea:
    code: str
    label: str
    path: str
    exists: bool
    size_bytes: int
    size_label: str
    note: str
    scan_truncated: bool = False
    files_scanned: int = 0
    directories_scanned: int = 0


@dataclass(frozen=True)
class BackupArchive:
    path: Path
    checksum_path: Path | None
    size_bytes: int
    mtime: float


TENANT_STORAGE_CATEGORIES: tuple[dict[str, Any], ...] = (
    {
        "code": "documents",
        "label": "Fascicoli e documenti",
        "note": "Atti, allegati fascicolo, output documentali e documenti AI.",
    },
    {
        "code": "email",
        "label": "Posta e allegati",
        "note": "PEC, email ordinaria, messaggi e allegati scaricati.",
    },
    {
        "code": "backup",
        "label": "Backup e mirror",
        "note": "Copie interne, mirror e snapshot dentro lo storage dello studio.",
    },
    {
        "code": "database",
        "label": "Database",
        "note": "Archivi SQLite e file strutturati dello studio.",
    },
    {
        "code": "intelligence",
        "label": "Lex e intelligence",
        "note": "Indici, fonti, giurisprudenza, copertura AI e cache di ricerca.",
    },
    {
        "code": "portal_imports",
        "label": "Portali e import",
        "note": "Acquisizioni autorizzate, staging telematico e pacchetti importati.",
    },
    {
        "code": "site_assets",
        "label": "Sito studio",
        "note": "Asset pubblici, contenuti e media del sito dello studio.",
    },
    {
        "code": "runtime_cache",
        "label": "Cache e code",
        "note": "Cache, OCR, Redis locale e file temporanei rigenerabili.",
    },
    {
        "code": "other",
        "label": "Altro da verificare",
        "note": "Dati non classificati nelle aree operative principali.",
    },
)
CATEGORY_META = {item["code"]: item for item in TENANT_STORAGE_CATEGORIES}
DB_FILE_SUFFIXES = {".db", ".sqlite", ".sqlite3"}


def human_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TiB"


def _sum_report_int(reports: list[dict[str, Any]], key: str) -> int:
    return sum(int(report.get(key, 0) or 0) for report in reports)


def _runtime_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    if config is not None:
        return config
    if has_app_context():
        return current_app.config
    return {}


def _config_int(config: dict[str, Any], name: str, default: int, *, legacy_name: str = "") -> int:
    raw = os.getenv(name)
    if raw is None and legacy_name:
        raw = os.getenv(legacy_name)
    if raw is None:
        raw = config.get(name)
    if raw is None and legacy_name:
        raw = config.get(legacy_name)
    try:
        value = int(str(raw if raw is not None else default).strip())
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _config_float(config: dict[str, Any], name: str, default: float, *, legacy_name: str = "") -> float:
    raw = os.getenv(name)
    if raw is None and legacy_name:
        raw = os.getenv(legacy_name)
    if raw is None:
        raw = config.get(name)
    if raw is None and legacy_name:
        raw = config.get(legacy_name)
    try:
        value = float(str(raw if raw is not None else default).strip().replace(",", "."))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def storage_scan_settings(config: dict[str, Any] | None = None) -> dict[str, int | float]:
    cfg = _runtime_config(config)
    return {
        "tenant_max_files": _config_int(
            cfg,
            "IUSENTRA_STORAGE_SCAN_MAX_FILES",
            DEFAULT_TENANT_STORAGE_SCAN_MAX_FILES,
        ),
        "tenant_seconds": _config_float(
            cfg,
            "IUSENTRA_STORAGE_SCAN_SECONDS",
            DEFAULT_TENANT_STORAGE_SCAN_SECONDS,
        ),
        "global_max_files": _config_int(
            cfg,
            "IUSENTRA_STORAGE_SCAN_GLOBAL_MAX_FILES",
            DEFAULT_GLOBAL_STORAGE_SCAN_MAX_FILES,
        ),
        "global_seconds": _config_float(
            cfg,
            "IUSENTRA_STORAGE_SCAN_GLOBAL_SECONDS",
            DEFAULT_GLOBAL_STORAGE_SCAN_SECONDS,
        ),
    }


def backup_retention_settings(config: dict[str, Any] | None = None) -> dict[str, int]:
    cfg = _runtime_config(config)
    min_count = _config_int(
        cfg,
        "IUSENTRA_BACKUP_RETENTION_MIN_COUNT",
        DEFAULT_BACKUP_RETENTION_MIN_COUNT,
        legacy_name="BACKUP_RETENTION_MIN_COUNT",
    )
    count = _config_int(
        cfg,
        "IUSENTRA_BACKUP_RETENTION_COUNT",
        DEFAULT_BACKUP_RETENTION_COUNT,
        legacy_name="BACKUP_RETENTION_COUNT",
    )
    return {
        "days": _config_int(
            cfg,
            "IUSENTRA_BACKUP_RETENTION_DAYS",
            DEFAULT_BACKUP_RETENTION_DAYS,
            legacy_name="BACKUP_RETENTION_DAYS",
        ),
        "count": max(count, min_count),
        "min_count": max(1, min_count),
        "max_gib": _config_int(
            cfg,
            "IUSENTRA_BACKUP_RETENTION_MAX_GIB",
            DEFAULT_BACKUP_RETENTION_MAX_GIB,
            legacy_name="BACKUP_RETENTION_MAX_GIB",
        ),
    }


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


def _bounded_directory_scan(
    paths: list[Path],
    *,
    max_files: int,
    time_budget_seconds: float,
) -> dict[str, Any]:
    """Scansione rapida per superfici interattive: evita blocchi su storage grandi."""

    deadline = time.monotonic() + max(time_budget_seconds, 0.05)
    seen: set[tuple[int, int]] = set()
    total = 0
    file_count = 0
    dir_count = 0
    truncated = False
    reason = ""

    for root in paths:
        if time.monotonic() >= deadline:
            truncated = True
            reason = "tempo massimo"
            break
        if not root.exists():
            continue
        if root.is_file():
            try:
                stat = root.stat()
            except OSError:
                continue
            if getattr(stat, "st_nlink", 1) > 1:
                inode_key = (stat.st_dev, stat.st_ino)
                if inode_key in seen:
                    continue
                seen.add(inode_key)
            total += int(stat.st_size)
            file_count += 1
            if file_count >= max_files:
                truncated = True
                reason = "limite file"
                break
            continue
        stack = [root]
        while stack:
            if time.monotonic() >= deadline:
                truncated = True
                reason = "tempo massimo"
                break
            current_root = stack.pop()
            try:
                entries = os.scandir(current_root)
            except OSError:
                continue
            with entries:
                for entry in entries:
                    if time.monotonic() >= deadline:
                        truncated = True
                        reason = "tempo massimo"
                        break
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            dir_count += 1
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if getattr(stat, "st_nlink", 1) > 1:
                        inode_key = (stat.st_dev, stat.st_ino)
                        if inode_key in seen:
                            continue
                        seen.add(inode_key)
                    total += int(stat.st_size)
                    file_count += 1
                    if file_count >= max_files:
                        truncated = True
                        reason = "limite file"
                        break
            if truncated:
                break
        if truncated:
            break

    return {
        "size_bytes": total,
        "file_count": file_count,
        "directory_count": dir_count,
        "truncated": truncated,
        "reason": reason,
    }


def resolve_data_root(config: dict[str, Any] | None = None) -> Path:
    cfg = _runtime_config(config)
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
    cfg = _runtime_config(config)
    return Path(
        str(
            os.getenv("IUSENTRA_BACKUP_DIR")
            or cfg.get("IUSENTRA_BACKUP_DIR")
            or "/opt/iusentra/backups"
        )
    )


def _backup_archives(backup_dir: str | Path) -> list[BackupArchive]:
    root = Path(backup_dir)
    if not root.is_dir():
        return []
    archives: list[BackupArchive] = []
    for path in root.glob("iusentra-data-*.tar.*"):
        if not path.is_file() or not any(str(path).endswith(suffix) for suffix in BACKUP_ARCHIVE_SUFFIXES):
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        checksum = Path(f"{path}.sha256")
        checksum_size = 0
        checksum_path = None
        if checksum.is_file():
            try:
                checksum_size = checksum.stat().st_size
                checksum_path = checksum
            except OSError:
                checksum_size = 0
        archives.append(
            BackupArchive(
                path=path,
                checksum_path=checksum_path,
                size_bytes=int(stat.st_size + checksum_size),
                mtime=float(stat.st_mtime),
            )
        )
    return sorted(archives, key=lambda item: item.mtime, reverse=True)


def run_backup_retention(
    *,
    apply: bool = False,
    backup_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Applica retention solo agli archivi backup governati di IUSENTRA."""

    cfg = _runtime_config(config)
    root = Path(backup_dir) if backup_dir is not None else resolve_external_backup_dir(cfg)
    settings = backup_retention_settings(cfg)
    archives = _backup_archives(root)
    total_before = sum(item.size_bytes for item in archives)
    protected = set(range(min(settings["min_count"], len(archives))))
    to_delete: set[int] = set()

    cutoff = datetime.now(timezone.utc).timestamp() - settings["days"] * 24 * 60 * 60
    for index, archive in enumerate(archives):
        if index in protected:
            continue
        if index >= settings["count"] or archive.mtime < cutoff:
            to_delete.add(index)

    max_bytes = settings["max_gib"] * 1024**3
    total_after = total_before - sum(archives[index].size_bytes for index in to_delete)
    remaining_count = len(archives) - len(to_delete)
    for index in range(len(archives) - 1, -1, -1):
        if total_after <= max_bytes or remaining_count <= settings["min_count"]:
            break
        if index in protected or index in to_delete:
            continue
        to_delete.add(index)
        total_after -= archives[index].size_bytes
        remaining_count -= 1

    planned = [archives[index] for index in sorted(to_delete, reverse=True)]
    bytes_reclaimable = sum(item.size_bytes for item in planned)
    deleted_archives = 0
    deleted_files = 0
    bytes_reclaimed = 0
    errors: list[str] = []
    if apply:
        for archive in planned:
            deleted_this_archive = False
            for candidate in (archive.path, archive.checksum_path):
                if candidate is None:
                    continue
                try:
                    size = candidate.stat().st_size
                    candidate.unlink()
                    deleted_files += 1
                    bytes_reclaimed += int(size)
                    deleted_this_archive = True
                except OSError as exc:
                    errors.append(f"{candidate.name}: {exc}")
            if deleted_this_archive:
                deleted_archives += 1

    total_after_effective = total_before - (bytes_reclaimed if apply else bytes_reclaimable)
    return {
        "mock_fallback": False,
        "applied": apply,
        "backup_dir": str(root),
        "backup_archives_scanned": len(archives),
        "archives_to_delete": len(planned),
        "archives_deleted": deleted_archives,
        "files_deleted": deleted_files,
        "bytes_total_before": total_before,
        "bytes_total_after": max(0, total_after_effective),
        "bytes_reclaimable": bytes_reclaimable,
        "bytes_reclaimed": bytes_reclaimed,
        "bytes_total_before_label": human_bytes(total_before),
        "bytes_total_after_label": human_bytes(max(0, total_after_effective)),
        "bytes_reclaimable_label": human_bytes(bytes_reclaimable),
        "bytes_reclaimed_label": human_bytes(bytes_reclaimed),
        "retention": settings,
        "errors": errors,
    }


def _scan_note(note: str, scan: dict[str, Any]) -> str:
    if not scan.get("truncated"):
        return note
    suffix = (
        f" Scansione rapida parziale per mantenere reattiva la console"
        f" ({scan.get('file_count', 0)} file letti, limite: {scan.get('reason') or 'operativo'})."
    )
    return f"{note}{suffix}" if note else suffix.strip()


def _area(
    code: str,
    label: str,
    path: Path,
    note: str = "",
    *,
    max_files: int = DEFAULT_GLOBAL_STORAGE_SCAN_MAX_FILES,
    time_budget_seconds: float = DEFAULT_GLOBAL_STORAGE_SCAN_SECONDS,
) -> StorageArea:
    exists = path.exists()
    scan = (
        _bounded_directory_scan([path], max_files=max_files, time_budget_seconds=time_budget_seconds)
        if exists
        else {"size_bytes": 0, "file_count": 0, "directory_count": 0, "truncated": False, "reason": ""}
    )
    size = int(scan["size_bytes"])
    return StorageArea(
        code=code,
        label=label,
        path=str(path),
        exists=exists,
        size_bytes=size,
        size_label=human_bytes(size),
        note=_scan_note(note, scan),
        scan_truncated=bool(scan.get("truncated")),
        files_scanned=int(scan.get("file_count", 0) or 0),
        directories_scanned=int(scan.get("directory_count", 0) or 0),
    )


def _area_from_size(
    code: str,
    label: str,
    path: Path,
    size: int,
    note: str = "",
    *,
    scan: dict[str, Any] | None = None,
) -> StorageArea:
    scan_data = scan or {"file_count": 0, "directory_count": 0, "truncated": False, "reason": ""}
    return StorageArea(
        code=code,
        label=label,
        path=str(path),
        exists=path.exists(),
        size_bytes=int(size),
        size_label=human_bytes(size),
        note=_scan_note(note, scan_data),
        scan_truncated=bool(scan_data.get("truncated")),
        files_scanned=int(scan_data.get("file_count", 0) or 0),
        directories_scanned=int(scan_data.get("directory_count", 0) or 0),
    )


def _category_for_file(relative_parts: tuple[str, ...], path: Path) -> str:
    first = relative_parts[0].lower() if relative_parts else ""
    second = relative_parts[1].lower() if len(relative_parts) > 1 else ""
    suffix = path.suffix.lower()

    if suffix in DB_FILE_SUFFIXES or first == "sql":
        return "database"
    if first in {"email", "messaggi", "comunicazioni"}:
        return "email"
    if first in {"backup", "backups"} or second in {"backup", "backups", "mirror"}:
        return "backup"
    if first in {"fascicoli", "documenti", "documenti_ai", "output", "template_atti", "wizard_pro"}:
        return "documents"
    if first in {"intelligence", "indexes", "lex", "legal_intelligence", "giurisprudenza", "search"}:
        return "intelligence"
    if first in {"portale", "telematico", "legal_deposit", "local_signer", "import", "imports", "uploads"}:
        return "portal_imports"
    if first in {"sito_studio", "site", "assets", "public_site", "static_site"}:
        return "site_assets"
    if first in {"redis", "cache", ".cache", "tmp", "temp", "ocr", "logs"}:
        return "runtime_cache"
    return "other"


def _folder_key(relative_parts: tuple[str, ...]) -> str:
    if not relative_parts:
        return "."
    first = relative_parts[0]
    if len(relative_parts) >= 2 and first.lower() in {
        "backup",
        "email",
        "fascicoli",
        "documenti",
        "documenti_ai",
        "intelligence",
        "indexes",
        "portale",
        "telematico",
        "legal_deposit",
        "sito_studio",
    }:
        return f"{first}/{relative_parts[1]}"
    return first


def _display_storage_path(value: str) -> str:
    return (
        value.replace("\\", "/")
        .replace("_repository", "_archivio")
        .replace("-repository", "-archivio")
        .replace("repository", "archivio")
    )


def _append_largest(items: list[dict[str, Any]], candidate: dict[str, Any], *, limit: int) -> None:
    items.append(candidate)
    items.sort(key=lambda item: int(item.get("size_bytes", 0) or 0), reverse=True)
    del items[limit:]


def _scan_tenant_storage(
    tenant_dir: Path,
    *,
    largest_limit: int = 8,
    top_limit: int = 8,
    max_files: int = DEFAULT_TENANT_STORAGE_SCAN_MAX_FILES,
    time_budget_seconds: float = DEFAULT_TENANT_STORAGE_SCAN_SECONDS,
) -> dict[str, Any]:
    """Scansione unica del tenant per spiegare dove finisce lo spazio disco."""

    total_size = 0
    file_count = 0
    dir_count = 0
    category_sizes = {item["code"]: 0 for item in TENANT_STORAGE_CATEGORIES}
    folder_sizes: dict[str, int] = {}
    largest_files: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    deadline = time.monotonic() + max(float(time_budget_seconds), 0.05)
    truncated = False
    limit_reason = ""

    if not tenant_dir.is_dir():
        return {
            "total_bytes": 0,
            "file_count": 0,
            "directory_count": 0,
            "categories": [
                {
                    **CATEGORY_META[code],
                    "size_bytes": 0,
                    "size_label": human_bytes(0),
                    "percent": 0,
                }
                for code in category_sizes
            ],
            "top_paths": [],
            "largest_files": [],
            "dominant_category": None,
            "scan_truncated": False,
            "scan_limit_reason": "",
        }

    stack = [tenant_dir]
    while stack:
        if time.monotonic() >= deadline:
            truncated = True
            limit_reason = "tempo massimo"
            break
        current_path = stack.pop()
        try:
            entries = os.scandir(current_path)
        except OSError:
            continue
        with entries:
            for entry in entries:
                if time.monotonic() >= deadline:
                    truncated = True
                    limit_reason = "tempo massimo"
                    break
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dir_count += 1
                        stack.append(Path(entry.path))
                        continue
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                path = Path(entry.path)
                if getattr(stat, "st_nlink", 1) > 1:
                    inode_key = (stat.st_dev, stat.st_ino)
                    if inode_key in seen:
                        continue
                    seen.add(inode_key)
                size = int(stat.st_size)
                file_count += 1
                total_size += size
                try:
                    relative = path.relative_to(tenant_dir)
                except ValueError:
                    relative = Path(path.name)
                parts = tuple(relative.parts)
                category = _category_for_file(parts, path)
                category_sizes[category] = category_sizes.get(category, 0) + size
                folder_key = _folder_key(parts)
                folder_sizes[folder_key] = folder_sizes.get(folder_key, 0) + size
                _append_largest(
                    largest_files,
                    {
                        "path": str(relative).replace("\\", "/"),
                        "display_path": _display_storage_path(str(relative).replace("\\", "/")),
                        "size_bytes": size,
                        "size_label": human_bytes(size),
                        "category": category,
                        "category_label": CATEGORY_META.get(category, CATEGORY_META["other"])["label"],
                        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime(
                            "%d/%m/%Y %H:%M UTC"
                        ),
                    },
                    limit=largest_limit,
                )
                if file_count >= max_files:
                    truncated = True
                    limit_reason = "limite file"
                    break
        if truncated:
            break

    categories = []
    for item in TENANT_STORAGE_CATEGORIES:
        size = int(category_sizes.get(item["code"], 0) or 0)
        categories.append(
            {
                **item,
                "size_bytes": size,
                "size_label": human_bytes(size),
                "percent": round((size / total_size) * 100, 1) if total_size else 0,
            }
        )
    categories.sort(key=lambda item: int(item["size_bytes"]), reverse=True)
    dominant_category = next((item for item in categories if int(item["size_bytes"]) > 0), None)
    top_paths = [
        {
            "path": path,
            "display_path": _display_storage_path(path),
            "size_bytes": size,
            "size_label": human_bytes(size),
            "percent": round((size / total_size) * 100, 1) if total_size else 0,
        }
        for path, size in sorted(folder_sizes.items(), key=lambda item: item[1], reverse=True)[:top_limit]
    ]
    return {
        "total_bytes": total_size,
        "file_count": file_count,
        "directory_count": dir_count,
        "categories": categories,
        "top_paths": top_paths,
        "largest_files": largest_files,
        "dominant_category": dominant_category,
        "scan_truncated": truncated,
        "scan_limit_reason": limit_reason,
        "scan_mode": "rapida parziale" if truncated else "completa",
    }


def _tenant_recommendations(scan: dict[str, Any]) -> list[str]:
    categories = {item["code"]: int(item.get("size_bytes", 0) or 0) for item in scan.get("categories", [])}
    recommendations: list[str] = []
    if scan.get("scan_truncated"):
        recommendations.append(
            "Scansione rapida parziale: aprire l'analisi dello studio per un controllo mirato completo."
        )
    dominant = scan.get("dominant_category") or {}
    if dominant:
        recommendations.append(f"Area principale: {dominant['label']} ({dominant['size_label']}).")
    if categories.get("backup", 0) > 256 * 1024**2:
        recommendations.append(
            "Backup e mirror sopra 256 MiB: analizzare retention e compattazione prima di creare nuove copie."
        )
    if categories.get("email", 0) > 256 * 1024**2:
        recommendations.append(
            "Posta e allegati sopra 256 MiB: deduplicare allegati e valutare archiviazione caselle chiuse."
        )
    if categories.get("database", 0) > 128 * 1024**2:
        recommendations.append("Database sopra 128 MiB: pianificare verifica integrita e VACUUM in manutenzione.")
    if categories.get("intelligence", 0) > 1024**3:
        recommendations.append("Lex e intelligence sopra 1 GiB: verificare indici, cache e fonti rigenerabili.")
    largest_files = scan.get("largest_files") or []
    if largest_files and int(largest_files[0].get("size_bytes", 0) or 0) > 1024**3:
        recommendations.append(
            f"File molto grande: {largest_files[0]['path']} pesa {largest_files[0]['size_label']}."
        )
    if not recommendations:
        recommendations.append("Nessuna manutenzione urgente rilevata.")
    return recommendations


def _tenant_primary_action(scan: dict[str, Any]) -> dict[str, str]:
    dominant = scan.get("dominant_category") or {}
    code = str(dominant.get("code", "") or "")
    if code == "backup":
        return {"label": "Analizza retention", "type": "retention"}
    if code in {"email", "backup"}:
        return {"label": "Analizza compattazione", "type": "compaction"}
    if code == "database":
        return {"label": "Apri archivio", "type": "database"}
    if code == "intelligence":
        return {"label": "Controlla Lex", "type": "lex"}
    return {"label": "Apri studio", "type": "detail"}


def _tenant_rows(
    data_root: Path,
    *,
    max_files: int = DEFAULT_TENANT_STORAGE_SCAN_MAX_FILES,
    time_budget_seconds: float = DEFAULT_TENANT_STORAGE_SCAN_SECONDS,
) -> list[dict[str, Any]]:
    tenants_root = data_root / "tenants"
    if not tenants_root.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for tenant_dir in sorted([item for item in tenants_root.iterdir() if item.is_dir()], key=lambda item: item.name):
        scan = _scan_tenant_storage(
            tenant_dir,
            max_files=max_files,
            time_budget_seconds=time_budget_seconds,
        )
        category_sizes = {item["code"]: int(item["size_bytes"]) for item in scan["categories"]}
        total_size = int(scan["total_bytes"])
        rows.append(
            {
                "slug": tenant_dir.name,
                "path": str(tenant_dir),
                "total_bytes": total_size,
                "total_label": human_bytes(total_size),
                "email_bytes": category_sizes.get("email", 0),
                "email_label": human_bytes(category_sizes.get("email", 0)),
                "backup_bytes": category_sizes.get("backup", 0),
                "backup_label": human_bytes(category_sizes.get("backup", 0)),
                "database_bytes": category_sizes.get("database", 0),
                "database_label": human_bytes(category_sizes.get("database", 0)),
                "documents_bytes": category_sizes.get("documents", 0),
                "documents_label": human_bytes(category_sizes.get("documents", 0)),
                "intelligence_bytes": category_sizes.get("intelligence", 0),
                "intelligence_label": human_bytes(category_sizes.get("intelligence", 0)),
                "runtime_cache_bytes": category_sizes.get("runtime_cache", 0),
                "runtime_cache_label": human_bytes(category_sizes.get("runtime_cache", 0)),
                "categories": scan["categories"],
                "top_paths": scan["top_paths"],
                "largest_files": scan["largest_files"],
                "file_count": scan["file_count"],
                "directory_count": scan["directory_count"],
                "scan_truncated": scan["scan_truncated"],
                "scan_limit_reason": scan["scan_limit_reason"],
                "scan_mode": scan["scan_mode"],
                "dominant_category": scan["dominant_category"],
                "primary_action": _tenant_primary_action(scan),
                "recommendations": _tenant_recommendations(scan),
                "links": {
                    "detail": f"/admin/studi/{tenant_dir.name}",
                    "database": f"/admin/studi/{tenant_dir.name}/database",
                    "users": f"/admin/studi/{tenant_dir.name}/utenti",
                },
            }
        )
    return sorted(rows, key=lambda row: int(row["total_bytes"]), reverse=True)


def _system_info() -> dict[str, Any]:
    try:
        import psutil
        mem = psutil.virtual_memory()
        load = psutil.getloadavg()
        return {
            "mem_total_label": human_bytes(mem.total),
            "mem_used_label": human_bytes(mem.used),
            "mem_percent": round(mem.percent, 1),
            "load_1": round(load[0], 2),
            "load_5": round(load[1], 2),
            "load_15": round(load[2], 2),
            "available": True,
        }
    except Exception:
        return {"available": False}


def build_server_maintenance_surface(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = _runtime_config(config)
    data_root = resolve_data_root(cfg)
    backup_dir = resolve_external_backup_dir(cfg)
    disk = shutil.disk_usage(data_root if data_root.exists() else Path("/"))
    scan_settings = storage_scan_settings(cfg)
    tenant_rows = _tenant_rows(
        data_root,
        max_files=int(scan_settings["tenant_max_files"]),
        time_budget_seconds=float(scan_settings["tenant_seconds"]),
    )
    email_roots = discover_email_attachment_roots(data_root)
    backup_roots = discover_backup_roots(data_root)
    global_email_roots = [path for path in email_roots if "tenants" not in path.parts]
    global_backup_roots = [path for path in backup_roots if "tenants" not in path.parts]
    tenant_email_size = sum(int(row.get("email_bytes", 0) or 0) for row in tenant_rows)
    global_email_scan = _bounded_directory_scan(
        global_email_roots,
        max_files=int(scan_settings["global_max_files"]),
        time_budget_seconds=float(scan_settings["global_seconds"]),
    )
    global_email_size = int(global_email_scan["size_bytes"])
    email_size = tenant_email_size + global_email_size
    tenant_backup_size = sum(int(row.get("backup_bytes", 0) or 0) for row in tenant_rows)
    global_backup_scan = _bounded_directory_scan(
        global_backup_roots,
        max_files=int(scan_settings["global_max_files"]),
        time_budget_seconds=float(scan_settings["global_seconds"]),
    )
    global_backup_size = int(global_backup_scan["size_bytes"])
    backup_mirror_size = tenant_backup_size + global_backup_size
    tenant_total_size = sum(int(row.get("total_bytes", 0) or 0) for row in tenant_rows)
    backup_archives = _backup_archives(backup_dir)
    backup_external_size = sum(item.size_bytes for item in backup_archives)
    retention_settings = backup_retention_settings(cfg)
    backup_retention = run_backup_retention(apply=False, backup_dir=backup_dir, config=cfg)
    tenant_scan_summary = {
        "truncated": any(row.get("scan_truncated") for row in tenant_rows),
        "reason": "limite operativo",
        "file_count": sum(int(row.get("file_count", 0) or 0) for row in tenant_rows),
        "directory_count": sum(int(row.get("directory_count", 0) or 0) for row in tenant_rows),
    }

    areas = [
        _area_from_size(
            "tenants",
            "Studi",
            data_root / "tenants",
            tenant_total_size,
            "Dati separati per studio.",
            scan=tenant_scan_summary,
        ),
        _area_from_size(
            "tenant_email",
            "Posta e allegati studi",
            data_root / "tenants",
            tenant_email_size,
            "Somma posta e allegati negli studi.",
            scan=tenant_scan_summary,
        ),
        _area_from_size(
            "backup_mirror",
            "Backup e mirror studi",
            data_root / "tenants",
            tenant_backup_size,
            "Snapshot, mirror e copie interne rilevate negli studi.",
            scan=tenant_scan_summary,
        ),
        _area_from_size(
            "global_email",
            "Posta area condivisa",
            data_root / "email",
            global_email_size,
            "Archivi email fuori studio: da mantenere solo in scenari mono-studio o migrazione.",
            scan=global_email_scan,
        ),
        _area_from_size(
            "global_backup",
            "Backup area condivisa",
            data_root / "backup",
            global_backup_size,
            "Copie backup fuori studio da governare con retention.",
            scan=global_backup_scan,
        ),
        _area(
            "email",
            "Allegati email globali",
            data_root / "email" / "allegati",
            "Allegati globali deduplicabili.",
            max_files=int(scan_settings["global_max_files"]),
            time_budget_seconds=float(scan_settings["global_seconds"]),
        ),
        _area(
            "ollama",
            "Modelli AI locali",
            data_root / "ollama",
            "Modelli Lex/Ollama locali.",
            max_files=int(scan_settings["global_max_files"]),
            time_budget_seconds=float(scan_settings["global_seconds"]),
        ),
        _area(
            "import",
            "Import portali",
            data_root / "portale",
            "Staging import autorizzati.",
            max_files=int(scan_settings["global_max_files"]),
            time_budget_seconds=float(scan_settings["global_seconds"]),
        ),
        _area(
            "redis",
            "Redis persistente",
            data_root / "redis",
            "Append-only file e snapshot Redis.",
            max_files=int(scan_settings["global_max_files"]),
            time_budget_seconds=float(scan_settings["global_seconds"]),
        ),
    ]
    recommendations = []
    used_ratio = disk.used / disk.total if disk.total else 0
    if tenant_scan_summary["truncated"] or global_email_scan["truncated"] or global_backup_scan["truncated"]:
        recommendations.append(
            "Scansione storage rapida: la console resta reattiva e mostra le aree principali; usare le analisi mirate quando serve il dettaglio completo."
        )
    if used_ratio >= 0.8:
        recommendations.append("Disco oltre l'80%: eseguire backup, compattazione e pulizia cache Docker.")
    if backup_external_size > retention_settings["max_gib"] * 1024**3:
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
            "scan_mode": "rapida",
            "scan_tenant_max_files": scan_settings["tenant_max_files"],
            "scan_tenant_seconds": scan_settings["tenant_seconds"],
            "scan_truncated": bool(
                tenant_scan_summary["truncated"] or global_email_scan["truncated"] or global_backup_scan["truncated"]
            ),
            "email_size_label": human_bytes(email_size),
            "backup_mirror_size_label": human_bytes(backup_mirror_size),
            "tenant_email_size_label": human_bytes(tenant_email_size),
            "tenant_backup_size_label": human_bytes(tenant_backup_size),
            "global_email_size_label": human_bytes(global_email_size),
            "global_backup_size_label": human_bytes(global_backup_size),
            "tenant_total_size_label": human_bytes(tenant_total_size),
            "backup_external_size_label": human_bytes(backup_external_size),
            "backup_archives_scanned": backup_retention["backup_archives_scanned"],
            "backup_retention_reclaimable_label": backup_retention["bytes_reclaimable_label"],
        },
        "backup_retention": backup_retention,
        "tenants": tenant_rows,
        "areas": [area.__dict__ for area in sorted(areas, key=lambda item: item.size_bytes, reverse=True)],
        "actions": {
            "analyze_compaction": "/admin/server-manutenzione/analizza-compattazione",
            "apply_compaction": "/admin/server-manutenzione/compatta",
            "analyze_backup_retention": "/admin/server-manutenzione/analizza-retention-backup",
            "apply_backup_retention": "/admin/server-manutenzione/applica-retention-backup",
        },
        "recommendations": recommendations,
        "last_backup": _last_backup_info(backup_dir),
        "system_info": _system_info(),
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


def trigger_backup(*, backup_script_path: str | Path | None = None) -> dict[str, Any]:
    """Lancia backup.sh in background e ritorna subito con un ticket."""
    import subprocess
    script = Path(backup_script_path or "").resolve() if backup_script_path else None
    if script is None or not script.exists():
        # Percorsi standard
        for candidate in [
            Path(__file__).resolve().parents[2] / "deploy" / "hetzner" / "backup.sh",
            Path("/opt/iusentra/repo/deploy/hetzner/backup.sh"),
        ]:
            if candidate.exists():
                script = candidate
                break
    if script is None:
        return {"ok": False, "error": "Script backup.sh non trovato.", "pid": None}
    log_path = Path("/tmp/iusentra-backup-trigger.log")
    try:
        proc = subprocess.Popen(
            ["/usr/bin/env", "bash", str(script)],
            stdout=log_path.open("w"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return {"ok": True, "pid": proc.pid, "log": str(log_path), "script": str(script)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "pid": None}


def run_docker_prune(*, dry_run: bool = True) -> dict[str, Any]:
    """Esegue docker system prune per liberare immagini e layer non usati."""
    import subprocess
    try:
        cmd = ["docker", "system", "df", "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        df_output = result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        df_output = ""

    if dry_run:
        return {
            "applied": False,
            "dry_run": True,
            "docker_df": df_output,
            "error": None,
        }
    try:
        prune = subprocess.run(
            ["docker", "system", "prune", "--volumes", "--force"],
            capture_output=True, text=True, timeout=120,
        )
        return {
            "applied": True,
            "dry_run": False,
            "stdout": prune.stdout,
            "error": prune.stderr if prune.returncode != 0 else None,
            "docker_df": df_output,
        }
    except Exception as exc:
        return {"applied": False, "dry_run": False, "docker_df": df_output, "error": str(exc)}


def _last_backup_info(backup_dir: str | Path | None = None) -> dict[str, Any]:
    """Ritorna info sull'ultimo backup disponibile."""
    root = Path(backup_dir) if backup_dir else resolve_external_backup_dir()
    archives = _backup_archives(root)
    if not archives:
        return {"found": False, "label": "Nessun backup", "path": None}
    last = archives[0]
    ts = datetime.fromtimestamp(last.mtime, tz=timezone.utc)
    return {
        "found": True,
        "label": ts.strftime("%d/%m/%Y %H:%M UTC"),
        "size_label": human_bytes(last.size_bytes),
        "path": str(last.path),
        "checksum": last.checksum_path is not None,
        "count": len(archives),
    }
