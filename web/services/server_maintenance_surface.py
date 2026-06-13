"""Superficie Superadmin per server, storage e manutenzione prestazionale."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import time
import uuid
from typing import Any

from flask import current_app, has_app_context

from pct.email_attachments import deduplicate_attachment_tree, discover_email_attachment_roots
from scripts.compact_iusentra_storage import discover_backup_roots

DEFAULT_BACKUP_RETENTION_DAYS = 14
DEFAULT_BACKUP_RETENTION_COUNT = 1
DEFAULT_BACKUP_RETENTION_MIN_COUNT = 1
DEFAULT_BACKUP_RETENTION_MAX_GIB = 8
MAX_BACKUP_RETENTION_COUNT = 3
DEFAULT_TENANT_STORAGE_SCAN_MAX_FILES = 12_000
DEFAULT_TENANT_STORAGE_SCAN_SECONDS = 0.9
DEFAULT_GLOBAL_STORAGE_SCAN_MAX_FILES = 6_000
DEFAULT_GLOBAL_STORAGE_SCAN_SECONDS = 0.45
DEFAULT_HOST_STORAGE_SCAN_MAX_FILES = 4_000
DEFAULT_HOST_STORAGE_SCAN_SECONDS = 0.75
BACKUP_ARCHIVE_SUFFIXES = (".tar.zst", ".tar.gz")
DOCKER_SOCKET_PATH = "/var/run/docker.sock"


def _public_runtime_error(message: str = "Operazione non completata.") -> str:
    return message


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


@dataclass(frozen=True)
class TenantBackupArchive:
    path: Path
    tenant_slug: str
    backup_dir: Path
    size_bytes: int
    mtime: float
    kind: str


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


def _parse_docker_size(value: Any) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    first = text.split()[0].replace(",", ".")
    number = "".join(ch for ch in first if ch.isdigit() or ch == ".")
    unit = first[len(number) :].strip() or "B"
    try:
        amount = float(number)
    except ValueError:
        return 0
    decimal_units = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "KiB": 1024,
        "MiB": 1024**2,
        "GiB": 1024**3,
        "TiB": 1024**4,
    }
    return int(amount * decimal_units.get(unit, 1))


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
    min_count = min(max(1, min_count), MAX_BACKUP_RETENTION_COUNT)
    count = min(max(count, min_count), MAX_BACKUP_RETENTION_COUNT)
    return {
        "days": _config_int(
            cfg,
            "IUSENTRA_BACKUP_RETENTION_DAYS",
            DEFAULT_BACKUP_RETENTION_DAYS,
            legacy_name="BACKUP_RETENTION_DAYS",
        ),
        "count": count,
        "min_count": min_count,
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


def _registry_path_for_data_root(data_root: Path, config: dict[str, Any]) -> Path:
    configured = (
        os.getenv("PCT_TENANTS_REGISTRY")
        or os.getenv("TENANTS_REGISTRY")
        or config.get("TENANTS_REGISTRY")
        or data_root / "tenants.json"
    )
    return Path(str(configured)).resolve()


def _registered_tenant_index(data_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    registry = _registry_path_for_data_root(data_root, config)
    if not registry.is_file():
        return {"available": False, "by_storage": {}, "aliases": {}, "path": str(registry)}
    try:
        raw = json.loads(registry.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False, "by_storage": {}, "aliases": {}, "path": str(registry)}

    if isinstance(raw, list):
        items = [(str(index), item) for index, item in enumerate(raw) if isinstance(item, dict)]
    elif isinstance(raw, dict) and isinstance(raw.get("tenants"), list):
        items = [
            (str(index), item)
            for index, item in enumerate(raw.get("tenants") or [])
            if isinstance(item, dict)
        ]
    elif isinstance(raw, dict):
        items = [(str(key), item) for key, item in raw.items() if isinstance(item, dict)]
    else:
        items = []

    by_storage: dict[str, dict[str, Any]] = {}
    aliases: dict[str, dict[str, Any]] = {}
    for key, item in items:
        directory = str(item.get("directory_dati") or "").strip()
        storage_key = str(item.get("storage_key") or "").strip()
        if not storage_key and directory:
            storage_key = Path(directory).name
        slug = str(item.get("slug") or key or storage_key).strip()
        storage_key = storage_key or slug or key
        state = str(item.get("stato") or ("ATTIVO" if item.get("attivo", True) is not False else "SOSPESO")).upper()
        active = item.get("attivo", True) is not False and state not in {"SOSPESO", "SCADUTO", "DISATTIVATO"}
        record = {
            "storage_key": storage_key,
            "slug": slug or storage_key,
            "name": str(item.get("nome") or item.get("name") or slug or storage_key).strip(),
            "state": state or "ATTIVO",
            "active": active,
            "registry_key": key,
        }
        by_storage[storage_key] = record
        if slug and slug != storage_key:
            aliases[slug] = record
    return {"available": True, "by_storage": by_storage, "aliases": aliases, "path": str(registry)}


def _tenant_dir_identity(tenant_dir: Path, registry_index: dict[str, Any]) -> dict[str, Any]:
    name = tenant_dir.name
    if not registry_index.get("available"):
        return {
            "registered": True,
            "active_registered": True,
            "storage_status": "registrata",
            "storage_status_label": "Studio registrato",
            "registry_slug": name,
            "canonical_storage_key": name,
            "display_name": name,
            "warning": "",
        }
    by_storage = dict(registry_index.get("by_storage") or {})
    aliases = dict(registry_index.get("aliases") or {})
    if name in by_storage:
        record = dict(by_storage[name])
        active = bool(record.get("active"))
        return {
            "registered": True,
            "active_registered": active,
            "storage_status": "attiva" if active else "non_attiva",
            "storage_status_label": "Studio attivo registrato" if active else "Studio registrato non attivo",
            "registry_slug": str(record.get("slug") or name),
            "canonical_storage_key": str(record.get("storage_key") or name),
            "display_name": str(record.get("name") or record.get("slug") or name),
            "warning": "",
        }
    if name in aliases:
        record = dict(aliases[name])
        return {
            "registered": False,
            "active_registered": False,
            "storage_status": "alias_legacy",
            "storage_status_label": "Cartella legacy non attiva",
            "registry_slug": str(record.get("slug") or name),
            "canonical_storage_key": str(record.get("storage_key") or ""),
            "display_name": str(record.get("name") or record.get("slug") or name),
            "warning": (
                "Cartella storica collegata allo slug dello studio: lo storage attivo e' "
                f"{record.get('storage_key') or 'quello registrato'}."
            ),
        }
    return {
        "registered": False,
        "active_registered": False,
        "storage_status": "non_registrata",
        "storage_status_label": "Cartella non registrata",
        "registry_slug": "",
        "canonical_storage_key": "",
        "display_name": name,
        "warning": "Cartella presente su disco ma assente dalla registry tenant: non e' conteggiata come studio attivo.",
    }


def resolve_host_root(config: dict[str, Any] | None = None) -> Path | None:
    cfg = _runtime_config(config)
    configured = os.getenv("IUSENTRA_HOST_ROOT") or cfg.get("IUSENTRA_HOST_ROOT")
    candidates = [configured, "/host"]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(str(candidate))
        if path.exists():
            return path.resolve()
    return None


def resolve_host_iusentra_dir(config: dict[str, Any] | None = None) -> Path | None:
    cfg = _runtime_config(config)
    configured = os.getenv("IUSENTRA_HOST_IUSENTRA_DIR") or cfg.get("IUSENTRA_HOST_IUSENTRA_DIR")
    if configured and Path(str(configured)).exists():
        return Path(str(configured)).resolve()
    host_root = resolve_host_root(cfg)
    if host_root:
        candidate = host_root / "opt" / "iusentra"
        if candidate.exists():
            return candidate.resolve()
    production_candidate = Path("/opt/iusentra")
    if production_candidate.exists():
        return production_candidate.resolve()
    return None


def _du_size(path: Path, *, timeout_seconds: float = 3.0) -> dict[str, Any]:
    if not path.exists():
        return {
            "size_bytes": 0,
            "size_label": human_bytes(0),
            "available": False,
            "estimated": False,
            "error": "",
        }
    try:
        import subprocess

        result = subprocess.run(
            ["du", "-sxB1", str(path)],
            capture_output=True,
            text=True,
            timeout=max(float(timeout_seconds), 0.25),
        )
        if result.returncode == 0 and result.stdout.strip():
            first = result.stdout.strip().split()[0]
            size = int(first)
            return {
                "size_bytes": size,
                "size_label": human_bytes(size),
                "available": True,
                "estimated": False,
                "error": "",
            }
    except Exception:
        pass
    scan = _bounded_directory_scan(
        [path],
        max_files=DEFAULT_HOST_STORAGE_SCAN_MAX_FILES,
        time_budget_seconds=DEFAULT_HOST_STORAGE_SCAN_SECONDS,
    )
    size = int(scan.get("size_bytes", 0) or 0)
    return {
        "size_bytes": size,
        "size_label": human_bytes(size),
        "available": True,
        "estimated": bool(scan.get("truncated")),
        "error": scan.get("reason", ""),
    }


def _decode_chunked_http_body(payload: bytes) -> bytes:
    chunks: list[bytes] = []
    position = 0
    while position < len(payload):
        line_end = payload.find(b"\r\n", position)
        if line_end < 0:
            break
        size_text = payload[position:line_end].split(b";", 1)[0].strip()
        try:
            size = int(size_text, 16)
        except ValueError:
            break
        position = line_end + 2
        if size == 0:
            break
        chunks.append(payload[position : position + size])
        position += size + 2
    return b"".join(chunks)


def _docker_api_request(method: str, path: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    socket_path = Path(os.getenv("IUSENTRA_DOCKER_SOCKET", DOCKER_SOCKET_PATH))
    if not socket_path.exists():
        return {"ok": False, "status": 0, "error": "Console container non collegata.", "body": ""}
    try:
        import socket

        request = (
            f"{method.upper()} {path} HTTP/1.1\r\n"
            "Host: docker\r\n"
            "Accept: application/json\r\n"
            "Content-Length: 0\r\n"
            "Connection: close\r\n\r\n"
        ).encode("ascii")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(max(float(timeout_seconds), 0.5))
            client.connect(str(socket_path))
            client.sendall(request)
            chunks: list[bytes] = []
            while True:
                try:
                    chunk = client.recv(65536)
                except TimeoutError:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
        raw = b"".join(chunks)
        header, _, body = raw.partition(b"\r\n\r\n")
        header_text = header.decode("iso-8859-1", errors="replace")
        status_line = header_text.splitlines()[0] if header_text else ""
        status = int(status_line.split()[1]) if len(status_line.split()) >= 2 else 0
        if "transfer-encoding: chunked" in header_text.lower():
            body = _decode_chunked_http_body(body)
        text = body.decode("utf-8", errors="replace")
        return {"ok": 200 <= status < 300, "status": status, "error": "", "body": text}
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Docker API non disponibile: %s", exc)
        return {"ok": False, "status": 0, "error": _public_runtime_error("Docker non disponibile."), "body": ""}


def _docker_df_from_api() -> dict[str, Any] | None:
    response = _docker_api_request("GET", "/system/df", timeout_seconds=5)
    if not response.get("ok"):
        return None
    try:
        raw = json.loads(str(response.get("body") or "{}"))
    except json.JSONDecodeError:
        return None
    build_items = raw.get("BuildCache") or []
    images = raw.get("Images") or []
    containers = raw.get("Containers") or []
    volumes = raw.get("Volumes") or []
    build_cache_size = sum(int(item.get("Size", 0) or 0) for item in build_items)
    build_cache_reclaimable = sum(
        int(item.get("Size", 0) or 0)
        for item in build_items
        if not bool(item.get("InUse"))
    )
    image_size = int(raw.get("LayersSize", 0) or 0)
    container_size = sum(int(item.get("SizeRw", 0) or 0) for item in containers)
    volume_size = sum(int((item.get("UsageData") or {}).get("Size", 0) or 0) for item in volumes)
    total_size = image_size + container_size + volume_size + build_cache_size
    return {
        "available": True,
        "source": "engine",
        "error": "",
        "images_count": len(images),
        "containers_count": len(containers),
        "volumes_count": len(volumes),
        "build_cache_count": len(build_items),
        "images_size_bytes": image_size,
        "containers_size_bytes": container_size,
        "volumes_size_bytes": volume_size,
        "build_cache_size_bytes": build_cache_size,
        "build_cache_reclaimable_bytes": build_cache_reclaimable,
        "total_size_bytes": total_size,
        "images_size_label": human_bytes(image_size),
        "containers_size_label": human_bytes(container_size),
        "volumes_size_label": human_bytes(volume_size),
        "build_cache_size_label": human_bytes(build_cache_size),
        "build_cache_reclaimable_label": human_bytes(build_cache_reclaimable),
        "total_size_label": human_bytes(total_size),
    }


def _docker_df_from_cli() -> dict[str, Any] | None:
    try:
        import subprocess

        result = subprocess.run(
            ["docker", "system", "df", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception:
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    rows = []
    for line in result.stdout.splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    by_type = {str(row.get("Type", "")).lower(): row for row in rows}
    images = by_type.get("images") or {}
    containers = by_type.get("containers") or {}
    volumes = by_type.get("local volumes") or {}
    build_cache = by_type.get("build cache") or {}
    images_size = _parse_docker_size(images.get("Size"))
    containers_size = _parse_docker_size(containers.get("Size"))
    volumes_size = _parse_docker_size(volumes.get("Size"))
    build_size = _parse_docker_size(build_cache.get("Size"))
    build_reclaimable = _parse_docker_size(build_cache.get("Reclaimable"))
    total_size = images_size + containers_size + volumes_size + build_size
    return {
        "available": True,
        "source": "cli",
        "error": "",
        "images_count": int(images.get("TotalCount", 0) or 0),
        "containers_count": int(containers.get("TotalCount", 0) or 0),
        "volumes_count": int(volumes.get("TotalCount", 0) or 0),
        "build_cache_count": int(build_cache.get("TotalCount", 0) or 0),
        "images_size_bytes": images_size,
        "containers_size_bytes": containers_size,
        "volumes_size_bytes": volumes_size,
        "build_cache_size_bytes": build_size,
        "build_cache_reclaimable_bytes": build_reclaimable,
        "total_size_bytes": total_size,
        "images_size_label": human_bytes(images_size),
        "containers_size_label": human_bytes(containers_size),
        "volumes_size_label": human_bytes(volumes_size),
        "build_cache_size_label": human_bytes(build_size),
        "build_cache_reclaimable_label": human_bytes(build_reclaimable),
        "total_size_label": human_bytes(total_size),
    }


def docker_storage_summary() -> dict[str, Any]:
    summary = _docker_df_from_api() or _docker_df_from_cli()
    if summary:
        return summary
    return {
        "available": False,
        "source": "",
        "error": "Console container non collegata.",
        "images_count": 0,
        "containers_count": 0,
        "volumes_count": 0,
        "build_cache_count": 0,
        "images_size_bytes": 0,
        "containers_size_bytes": 0,
        "volumes_size_bytes": 0,
        "build_cache_size_bytes": 0,
        "build_cache_reclaimable_bytes": 0,
        "total_size_bytes": 0,
        "images_size_label": human_bytes(0),
        "containers_size_label": human_bytes(0),
        "volumes_size_label": human_bytes(0),
        "build_cache_size_label": human_bytes(0),
        "build_cache_reclaimable_label": human_bytes(0),
        "total_size_label": human_bytes(0),
    }


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
                    if has_app_context():
                        current_app.logger.warning("Rimozione archivio backup non completata per %s: %s", candidate, exc)
                    errors.append(f"{candidate.name}: archivio non rimosso")
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


def _zip_contains_operational_documents(path: Path) -> bool:
    try:
        import zipfile

        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    except Exception:
        return False
    return any(name.startswith(("fascicoli/", "documenti/", "archivio/")) for name in names)


def _tenant_backup_roots(data_root: Path, tenant_slug: str = "") -> list[Path]:
    tenants_root = data_root / "tenants"
    slug = str(tenant_slug or "").strip()
    if slug:
        root = tenants_root / slug / "backup"
        return [root] if root.is_dir() else []
    if not tenants_root.is_dir():
        return []
    return sorted(
        [item / "backup" for item in tenants_root.iterdir() if (item / "backup").is_dir()],
        key=lambda item: str(item),
    )


def _tenant_backup_archives(data_root: Path, tenant_slug: str = "") -> list[TenantBackupArchive]:
    archives: list[TenantBackupArchive] = []
    for backup_root in _tenant_backup_roots(data_root, tenant_slug):
        tenant_name = backup_root.parent.name
        for path in backup_root.glob("*.zip"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            kind = "temporaneo" if path.name.endswith("_tmp.zip") else (
                "completo" if _zip_contains_operational_documents(path) else "incrementale"
            )
            archives.append(
                TenantBackupArchive(
                    path=path,
                    tenant_slug=tenant_name,
                    backup_dir=backup_root,
                    size_bytes=int(stat.st_size),
                    mtime=float(stat.st_mtime),
                    kind=kind,
                )
            )
    return sorted(archives, key=lambda item: item.mtime, reverse=True)


def _prune_backup_registry(backup_dir: Path, keep_path: Path | None) -> None:
    registry = backup_dir / "registro.json"
    if keep_path is None or not registry.is_file():
        return
    try:
        payload = json.loads(registry.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(payload, list):
        return
    keep_name = keep_path.name
    filtered = [
        item
        for item in payload
        if isinstance(item, dict) and Path(str(item.get("percorso_file") or "")).name == keep_name
    ]
    if filtered:
        registry.write_text(json.dumps(filtered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_tenant_backup_retention(
    *,
    apply: bool = False,
    data_root: str | Path | None = None,
    tenant_slug: str = "",
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Conserva una sola copia completa per gli archivi backup interni agli studi."""

    cfg = _runtime_config(config)
    root = Path(data_root) if data_root else resolve_data_root(cfg)
    settings = backup_retention_settings(cfg)
    archives = _tenant_backup_archives(root, tenant_slug)
    by_backup_dir: dict[Path, list[TenantBackupArchive]] = {}
    for archive in archives:
        by_backup_dir.setdefault(archive.backup_dir, []).append(archive)

    planned: list[TenantBackupArchive] = []
    protected_paths: set[Path] = set()
    for backup_dir, rows in by_backup_dir.items():
        complete_rows = [item for item in rows if item.kind == "completo"]
        keep = max(complete_rows or rows, key=lambda item: item.mtime, default=None)
        if keep:
            protected_paths.add(keep.path.resolve())
        for item in rows:
            if item.path.resolve() in protected_paths:
                continue
            planned.append(item)

    mirror_dirs = [root_path / "mirror" for root_path in by_backup_dir if (root_path / "mirror").is_dir()]
    mirror_bytes = sum(directory_size(path) for path in mirror_dirs)
    bytes_reclaimable = sum(item.size_bytes for item in planned) + mirror_bytes
    deleted_archives = 0
    deleted_files = 0
    deleted_mirror_dirs = 0
    bytes_reclaimed = 0
    errors: list[str] = []

    if apply:
        for archive in planned:
            try:
                size = archive.path.stat().st_size
                archive.path.unlink()
                deleted_archives += 1
                deleted_files += 1
                bytes_reclaimed += int(size)
            except OSError as exc:
                if has_app_context():
                    current_app.logger.warning("Rimozione archivio tenant non completata per %s: %s", archive.path, exc)
                errors.append(f"{archive.path.name}: archivio non rimosso")
        for backup_dir, rows in by_backup_dir.items():
            complete_rows = [item for item in rows if item.kind == "completo" and item.path.exists()]
            keep = max(complete_rows or [item for item in rows if item.path.exists()], key=lambda item: item.mtime, default=None)
            _prune_backup_registry(backup_dir, keep.path if keep else None)
        for mirror_dir in mirror_dirs:
            try:
                size = directory_size(mirror_dir)
                shutil.rmtree(mirror_dir)
                deleted_mirror_dirs += 1
                bytes_reclaimed += int(size)
            except OSError as exc:
                if has_app_context():
                    current_app.logger.warning("Rimozione mirror backup non completata per %s: %s", mirror_dir, exc)
                errors.append(f"{mirror_dir}: cartella non rimossa")

    return {
        "mock_fallback": False,
        "applied": apply,
        "data_root": str(root),
        "tenant_slug": str(tenant_slug or "").strip(),
        "tenant_backup_roots": len(by_backup_dir),
        "backup_archives_scanned": len(archives),
        "archives_to_delete": len(planned),
        "archives_deleted": deleted_archives,
        "files_deleted": deleted_files,
        "mirror_dirs_to_delete": len(mirror_dirs),
        "mirror_dirs_deleted": deleted_mirror_dirs,
        "bytes_reclaimable": bytes_reclaimable,
        "bytes_reclaimed": bytes_reclaimed,
        "bytes_reclaimable_label": human_bytes(bytes_reclaimable),
        "bytes_reclaimed_label": human_bytes(bytes_reclaimed),
        "retention": settings,
        "kept_archives": [
            {
                "tenant_slug": item.tenant_slug,
                "path": str(item.path),
                "name": item.path.name,
                "kind": item.kind,
                "size_label": human_bytes(item.size_bytes),
            }
            for item in archives
            if item.path.resolve() in protected_paths
        ],
        "errors": errors,
    }


def run_all_backup_retention(
    *,
    apply: bool = False,
    config: dict[str, Any] | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    """Applica la retention governata a backup esterni e backup interni tenant."""

    cfg = _runtime_config(config)
    external = run_backup_retention(apply=apply, config=cfg)
    tenant = run_tenant_backup_retention(apply=apply, config=cfg, tenant_slug=tenant_slug)
    archives_scanned = int(external.get("backup_archives_scanned", 0) or 0) + int(
        tenant.get("backup_archives_scanned", 0) or 0
    )
    archives_to_delete = int(external.get("archives_to_delete", 0) or 0) + int(
        tenant.get("archives_to_delete", 0) or 0
    )
    archives_deleted = int(external.get("archives_deleted", 0) or 0) + int(
        tenant.get("archives_deleted", 0) or 0
    )
    reclaimable = int(external.get("bytes_reclaimable", 0) or 0) + int(
        tenant.get("bytes_reclaimable", 0) or 0
    )
    reclaimed = int(external.get("bytes_reclaimed", 0) or 0) + int(tenant.get("bytes_reclaimed", 0) or 0)
    errors = list(external.get("errors") or []) + list(tenant.get("errors") or [])
    return {
        "mock_fallback": False,
        "applied": apply,
        "backup_dir": str(external.get("backup_dir") or ""),
        "backup_archives_scanned": archives_scanned,
        "archives_to_delete": archives_to_delete,
        "archives_deleted": archives_deleted,
        "files_deleted": int(external.get("files_deleted", 0) or 0) + int(tenant.get("files_deleted", 0) or 0),
        "bytes_total_before": int(external.get("bytes_total_before", 0) or 0),
        "bytes_total_after": int(external.get("bytes_total_after", 0) or 0),
        "bytes_reclaimable": reclaimable,
        "bytes_reclaimed": reclaimed,
        "bytes_total_before_label": external.get("bytes_total_before_label") or human_bytes(0),
        "bytes_total_after_label": external.get("bytes_total_after_label") or human_bytes(0),
        "bytes_reclaimable_label": human_bytes(reclaimable),
        "bytes_reclaimed_label": human_bytes(reclaimed),
        "retention": backup_retention_settings(cfg),
        "external": external,
        "tenant": tenant,
        "errors": errors,
    }


def run_inactive_tenant_cleanup(
    *,
    apply: bool = False,
    data_root: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rimuove cartelle tenant non operative: alias legacy e directory fuori registry."""

    cfg = _runtime_config(config)
    root = Path(data_root) if data_root else resolve_data_root(cfg)
    tenants_root = root / "tenants"
    registry_index = _registered_tenant_index(root, cfg)
    candidates: list[dict[str, Any]] = []
    errors: list[str] = []
    if tenants_root.is_dir() and registry_index.get("available"):
        for tenant_dir in sorted([item for item in tenants_root.iterdir() if item.is_dir()], key=lambda item: item.name):
            identity = _tenant_dir_identity(tenant_dir, registry_index)
            if bool(identity.get("active_registered")):
                continue
            size = directory_size(tenant_dir)
            candidates.append(
                {
                    "slug": tenant_dir.name,
                    "path": str(tenant_dir),
                    "status": identity["storage_status"],
                    "status_label": identity["storage_status_label"],
                    "warning": identity["warning"],
                    "size_bytes": size,
                    "size_label": human_bytes(size),
                }
            )

    removed = 0
    bytes_reclaimed = 0
    if apply:
        for item in candidates:
            target = Path(str(item.get("path") or "")).resolve()
            try:
                if not str(target).startswith(str(tenants_root.resolve()) + os.sep):
                    errors.append(f"{target}: percorso fuori dallo storage tenant")
                    continue
                if not target.is_dir():
                    continue
                size = directory_size(target)
                shutil.rmtree(target)
                removed += 1
                bytes_reclaimed += int(size)
            except OSError as exc:
                if has_app_context():
                    current_app.logger.warning("Rimozione tenant inattivo non completata per %s: %s", target, exc)
                errors.append(f"{target}: cartella non rimossa")

    reclaimable = sum(int(item.get("size_bytes", 0) or 0) for item in candidates)
    return {
        "mock_fallback": False,
        "applied": apply,
        "data_root": str(root),
        "candidates": candidates,
        "candidates_count": len(candidates),
        "directories_deleted": removed,
        "bytes_reclaimable": reclaimable,
        "bytes_reclaimed": bytes_reclaimed,
        "bytes_reclaimable_label": human_bytes(reclaimable),
        "bytes_reclaimed_label": human_bytes(bytes_reclaimed),
        "errors": errors,
    }


def run_temporary_snapshot_cleanup(
    *,
    apply: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _runtime_config(config)
    host_iusentra = resolve_host_iusentra_dir(cfg)
    target = (host_iusentra / "tmp-backup-snapshot") if host_iusentra else None
    size = directory_size(target) if target and target.exists() else 0
    removed = False
    error = ""
    if apply and target and target.exists():
        try:
            shutil.rmtree(target)
            removed = True
        except OSError as exc:
            if has_app_context():
                current_app.logger.warning("Pulizia snapshot temporaneo non completata: %s", exc)
            error = _public_runtime_error("Snapshot temporaneo non rimosso.")
    return {
        "mock_fallback": False,
        "applied": apply,
        "path": str(target or ""),
        "exists": bool(target and target.exists()) if not removed else False,
        "bytes_reclaimable": size,
        "bytes_reclaimed": size if removed else 0,
        "bytes_reclaimable_label": human_bytes(size),
        "bytes_reclaimed_label": human_bytes(size if removed else 0),
        "deleted": removed,
        "errors": [error] if error else [],
    }


def resolve_normativa_root(config: dict[str, Any] | None = None) -> Path:
    cfg = _runtime_config(config)
    configured = (
        os.getenv("PCT_NORMATTIVA_DB")
        or os.getenv("PCT_LEX_NORMATTIVA_DB")
        or str(cfg.get("NORMATTIVA_DB") or "").strip()
    )
    if configured:
        path = Path(configured)
        return path.parent if path.name else path
    return resolve_data_root(cfg) / "normativa"


def run_normativa_global_cleanup(
    *,
    apply: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rimuove solo backup duplicati Normattiva, lasciando vivi DB, indice e sorgenti."""

    cfg = _runtime_config(config)
    root = resolve_normativa_root(cfg)
    backup_dir = root / "backups"
    db_path = Path(str(cfg.get("NORMATTIVA_DB") or root / "normattiva.sqlite"))
    jsonl_path = Path(str(cfg.get("NORMATTIVA_JSONL") or root / "index" / "normattiva_chunks.jsonl"))
    size = directory_size(backup_dir) if backup_dir.is_dir() else 0
    deleted = False
    errors: list[str] = []
    if apply and backup_dir.is_dir():
        try:
            resolved_root = root.resolve()
            resolved_target = backup_dir.resolve()
            if resolved_target.name != "backups" or not str(resolved_target).startswith(str(resolved_root) + os.sep):
                errors.append(f"{resolved_target}: percorso backup Normattiva non sicuro")
            else:
                shutil.rmtree(resolved_target)
                deleted = True
        except OSError as exc:
            if has_app_context():
                current_app.logger.warning("Rimozione backup Normattiva non completata per %s: %s", backup_dir, exc)
            errors.append(f"{backup_dir}: cartella non rimossa")

    return {
        "mock_fallback": False,
        "applied": apply,
        "normativa_root": str(root),
        "backup_dir": str(backup_dir),
        "backup_dir_exists": bool(backup_dir.exists()) if not deleted else False,
        "live_db_path": str(db_path),
        "live_db_exists": db_path.exists(),
        "index_path": str(jsonl_path),
        "index_exists": jsonl_path.exists(),
        "backup_dirs_scanned": 1 if backup_dir.exists() or deleted else 0,
        "directories_deleted": 1 if deleted else 0,
        "bytes_reclaimable": size,
        "bytes_reclaimed": size if deleted else 0,
        "bytes_reclaimable_label": human_bytes(size),
        "bytes_reclaimed_label": human_bytes(size if deleted else 0),
        "errors": errors,
    }


def run_system_log_cleanup(
    *,
    apply: bool = False,
    max_size: str = "256M",
) -> dict[str, Any]:
    """Riduce i journal di sistema senza toccare dati applicativi o container."""

    before_text = ""
    after_text = ""
    error = ""
    try:
        import subprocess

        before = subprocess.run(
            ["journalctl", "--disk-usage"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        before_text = before.stdout.strip() or before.stderr.strip()
        if apply:
            vacuum = subprocess.run(
                ["journalctl", f"--vacuum-size={max_size}"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if vacuum.returncode != 0:
                error = vacuum.stderr.strip() or vacuum.stdout.strip() or "Pulizia log non completata."
        after = subprocess.run(
            ["journalctl", "--disk-usage"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        after_text = after.stdout.strip() or after.stderr.strip()
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Pulizia journal di sistema non completata: %s", exc)
        error = _public_runtime_error("Pulizia log di sistema non completata.")
    return {
        "mock_fallback": False,
        "applied": apply,
        "max_size": max_size,
        "before": before_text,
        "after": after_text,
        "bytes_reclaimable": 0,
        "bytes_reclaimed": 0,
        "bytes_reclaimable_label": "calcolato dal sistema",
        "bytes_reclaimed_label": "calcolato dal sistema",
        "errors": [error] if error else [],
    }


def run_professional_server_maintenance(
    *,
    apply: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Manutenzione superadmin end-to-end sulle sole aree rigenerabili o non operative."""

    cfg = _runtime_config(config)
    backup = run_all_backup_retention(apply=apply, config=cfg)
    inactive = run_inactive_tenant_cleanup(apply=apply, config=cfg)
    snapshot = run_temporary_snapshot_cleanup(apply=apply, config=cfg)
    normativa = run_normativa_global_cleanup(apply=apply, config=cfg)
    logs = run_system_log_cleanup(apply=apply)
    docker = run_docker_prune(dry_run=not apply)
    reclaimed = (
        int(backup.get("bytes_reclaimed" if apply else "bytes_reclaimable", 0) or 0)
        + int(inactive.get("bytes_reclaimed" if apply else "bytes_reclaimable", 0) or 0)
        + int(snapshot.get("bytes_reclaimed" if apply else "bytes_reclaimable", 0) or 0)
        + int(normativa.get("bytes_reclaimed" if apply else "bytes_reclaimable", 0) or 0)
        + int(docker.get("bytes_reclaimed" if apply else "bytes_reclaimable", 0) or 0)
    )
    errors = (
        list(backup.get("errors") or [])
        + list(inactive.get("errors") or [])
        + list(snapshot.get("errors") or [])
        + list(normativa.get("errors") or [])
        + list(logs.get("errors") or [])
        + ([str(docker.get("error"))] if docker.get("error") else [])
    )
    return {
        "mock_fallback": False,
        "applied": apply,
        "bytes_reclaimable": reclaimed if not apply else 0,
        "bytes_reclaimed": reclaimed if apply else 0,
        "bytes_reclaimable_label": human_bytes(reclaimed if not apply else 0),
        "bytes_reclaimed_label": human_bytes(reclaimed if apply else 0),
        "backup_retention": backup,
        "inactive_tenants": inactive,
        "temporary_snapshot": snapshot,
        "normativa_global": normativa,
        "system_logs": logs,
        "docker_prune": docker,
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
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    tenants_root = data_root / "tenants"
    if not tenants_root.is_dir():
        return []
    registry_index = _registered_tenant_index(data_root, _runtime_config(config))
    rows: list[dict[str, Any]] = []
    for tenant_dir in sorted([item for item in tenants_root.iterdir() if item.is_dir()], key=lambda item: item.name):
        identity = _tenant_dir_identity(tenant_dir, registry_index)
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
                "display_name": identity["display_name"],
                "registry_slug": identity["registry_slug"],
                "canonical_storage_key": identity["canonical_storage_key"],
                "registered": identity["registered"],
                "active_registered": identity["active_registered"],
                "storage_status": identity["storage_status"],
                "storage_status_label": identity["storage_status_label"],
                "storage_warning": identity["warning"],
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
                    "detail": f"/admin/studi/{identity['registry_slug'] or tenant_dir.name}",
                    "database": f"/admin/studi/{identity['registry_slug'] or tenant_dir.name}/database",
                    "users": f"/admin/studi/{identity['registry_slug'] or tenant_dir.name}/utenti",
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


def _host_area(code: str, label: str, path: Path | None, note: str) -> dict[str, Any]:
    if path is None:
        size = {
            "size_bytes": 0,
            "size_label": human_bytes(0),
            "available": False,
            "estimated": False,
            "error": "",
        }
        resolved = ""
    else:
        size = _du_size(path)
        resolved = str(path)
    return {
        "code": code,
        "label": label,
        "path": resolved,
        "exists": bool(path is not None and path.exists()),
        "size_bytes": int(size.get("size_bytes", 0) or 0),
        "size_label": str(size.get("size_label") or human_bytes(0)),
        "estimated": bool(size.get("estimated")),
        "note": note,
    }


def _platform_data_children(data_root: Path, *, platform_outside_size: int, limit: int = 8) -> tuple[list[dict[str, Any]], int]:
    if not data_root.is_dir():
        return [], 0
    rows: list[dict[str, Any]] = []
    for child in sorted(data_root.iterdir(), key=lambda item: item.name):
        if child.name == "tenants":
            continue
        size = int(_du_size(child, timeout_seconds=1.5).get("size_bytes", 0) or 0)
        if size <= 0:
            continue
        label = f"Dati globali: {child.name}"
        note = "Area dati piattaforma fuori dagli storage tenant attivi."
        tone = "warning" if child.name in {"normativa", "ollama", "intelligence"} else "neutral"
        if child.name == "normativa":
            backup_size = directory_size(child / "backups") if (child / "backups").is_dir() else 0
            label = "Dati globali: normativa"
            note = "Archivio Normattiva globale usato da Ricerca Legale e Lex: DB, indice e sorgenti restano vivi."
            if backup_size:
                note = f"{note} Backup duplicati pulibili: {human_bytes(backup_size)}."
            tone = "warning" if backup_size else "success"
        elif child.name == "intelligence":
            note = "Repository globale di ricerca e aggiornamenti legali condivisi dal prodotto."
        elif child.name == "ollama":
            note = "Modelli AI locali: rimuovere solo da Impostazioni AI se non vengono usati."
        rows.append(
            {
                "code": f"data_{child.name}",
                "label": label,
                "size_bytes": size,
                "size_label": human_bytes(size),
                "note": note,
                "tone": tone,
            }
        )
    rows.sort(key=lambda item: int(item.get("size_bytes", 0) or 0), reverse=True)
    visible = rows[:limit]
    visible_total = sum(int(item.get("size_bytes", 0) or 0) for item in visible)
    other_size = max(0, int(platform_outside_size) - visible_total)
    return visible, other_size


def build_host_console(
    *,
    config: dict[str, Any] | None,
    data_root: Path,
    backup_dir: Path,
    disk: shutil._ntuple_diskusage,
    tenant_total_size: int,
    backup_external_size: int,
) -> dict[str, Any]:
    cfg = _runtime_config(config)
    provider_name = str(
        os.getenv("IUSENTRA_SERVER_PROVIDER_NAME") or cfg.get("IUSENTRA_SERVER_PROVIDER_NAME") or "Hetzner CPX42"
    )
    host_root = resolve_host_root(cfg)
    host_iusentra = resolve_host_iusentra_dir(cfg)
    docker = docker_storage_summary()
    disk_path = host_root or (data_root if data_root.exists() else Path("/"))
    try:
        host_disk = shutil.disk_usage(disk_path)
    except OSError:
        host_disk = disk

    def iusentra_child(name: str) -> Path | None:
        if host_iusentra is None:
            return None
        candidate = host_iusentra / name
        return candidate if candidate.exists() else None

    areas = [
        _host_area(
            "platform_data",
            "Dati piattaforma",
            iusentra_child("data") or (data_root if data_root.exists() else None),
            "Dati operativi, tenant, fonti ufficiali e indici di ricerca.",
        ),
        _host_area(
            "external_backups",
            "Archivi backup esterni",
            iusentra_child("backups") or (backup_dir if backup_dir.exists() else None),
            "Copie gia' presenti fuori dagli studi, governate da retention.",
        ),
        _host_area(
            "temporary_snapshot",
            "Snapshot temporaneo residuo",
            iusentra_child("tmp-backup-snapshot"),
            "Area temporanea da verificare: se non collegata ai container puo' essere rimossa.",
        ),
        _host_area(
            "repository",
            "Codice applicativo",
            iusentra_child("repo"),
            "Sorgenti di deploy e asset compilati.",
        ),
        _host_area(
            "caddy",
            "Proxy HTTPS",
            iusentra_child("caddy_data"),
            "Certificati e dati del proxy pubblico.",
        ),
        _host_area(
            "server_logs",
            "Log server",
            (host_root / "var" / "log") if host_root and (host_root / "var" / "log").exists() else None,
            "Log di sistema e servizi.",
        ),
    ]
    areas.sort(key=lambda item: int(item.get("size_bytes", 0) or 0), reverse=True)

    snapshot = next((area for area in areas if area["code"] == "temporary_snapshot"), None) or {}
    snapshot_bytes = int(snapshot.get("size_bytes", 0) or 0)
    docker_reclaimable = int(docker.get("build_cache_reclaimable_bytes", 0) or 0)
    normativa_cleanup = run_normativa_global_cleanup(apply=False, config=cfg)
    normativa_reclaimable = int(normativa_cleanup.get("bytes_reclaimable", 0) or 0)
    retention_reclaimable = max(
        0,
        int(backup_external_size) - backup_retention_settings(cfg)["max_gib"] * 1024**3,
    )
    immediate_reclaimable = docker_reclaimable + normativa_reclaimable
    review_reclaimable = snapshot_bytes + retention_reclaimable
    outside_tenants = max(0, int(host_disk.used) - int(tenant_total_size))
    docker_total = int(docker.get("total_size_bytes", 0) or 0)
    platform_area = next((area for area in areas if area["code"] == "platform_data"), {}) or {}
    platform_outside = max(0, int(platform_area.get("size_bytes", 0) or 0) - int(tenant_total_size))
    platform_children, platform_other = _platform_data_children(
        data_root,
        platform_outside_size=platform_outside,
    )
    outside_known = docker_total + platform_outside + sum(
        int(area.get("size_bytes", 0) or 0)
        for area in areas
        if area.get("code") not in {"platform_data"}
    )
    outside_unclassified = max(0, outside_tenants - outside_known)
    explained_total = outside_known
    outside_breakdown = [
        *platform_children,
        {
            "code": "platform_shared_other",
            "label": "Altri dati piattaforma fuori studi",
            "size_bytes": platform_other,
            "size_label": human_bytes(platform_other),
            "note": "Residuo delle aree globali sotto data dopo le voci principali.",
            "tone": "neutral",
        },
        {
            "code": "docker_storage",
            "label": "Docker e servizi",
            "size_bytes": docker_total,
            "size_label": human_bytes(docker_total),
            "note": "Immagini, container, volumi e cache. La cache costruzione e' pulibile dalla console.",
            "tone": "success" if docker_reclaimable else "neutral",
        },
    ]
    for area in areas:
        if area.get("code") == "platform_data":
            continue
        outside_breakdown.append(
            {
                "code": area.get("code"),
                "label": area.get("label"),
                "size_bytes": int(area.get("size_bytes", 0) or 0),
                "size_label": area.get("size_label"),
                "note": area.get("note"),
                "tone": "warning" if area.get("code") in {"temporary_snapshot", "external_backups"} else "neutral",
            }
        )
    if outside_unclassified:
        outside_breakdown.append(
            {
                "code": "system_unclassified",
                "label": "Sistema operativo e spazio non classificato",
                "size_bytes": outside_unclassified,
                "size_label": human_bytes(outside_unclassified),
                "note": "Quota residua del disco: sistema operativo, librerie, journald, pacchetti e file non sotto IUSENTRA.",
                "tone": "neutral",
            }
        )
    outside_breakdown = [item for item in outside_breakdown if int(item.get("size_bytes", 0) or 0) > 0]
    outside_breakdown.sort(key=lambda item: int(item.get("size_bytes", 0) or 0), reverse=True)

    recovery_items: list[dict[str, Any]] = []
    if docker_reclaimable:
        recovery_items.append(
            {
                "label": "Cache costruzione servizi",
                "size_label": human_bytes(docker_reclaimable),
                "tone": "success",
                "action": "Pulizia cache servizi",
                "note": "Recupero sicuro: non tocca dati studio e rende solo piu' lenta la prossima ricostruzione.",
            }
        )
    if normativa_reclaimable:
        recovery_items.append(
            {
                "label": "Backup duplicati Normattiva",
                "size_label": human_bytes(normativa_reclaimable),
                "tone": "success",
                "action": "Pulizia backup normativa",
                "note": "Recupero sicuro: lascia vivi DB, indice e sorgenti usati da Ricerca Legale e Lex.",
            }
        )
    if snapshot_bytes:
        recovery_items.append(
            {
                "label": "Snapshot temporaneo residuo",
                "size_label": human_bytes(snapshot_bytes),
                "tone": "warning",
                "action": "Verifica residuo",
                "note": "Da rimuovere solo dopo controllo che non sia montato o usato dai container.",
            }
        )
    if retention_reclaimable:
        recovery_items.append(
            {
                "label": "Backup oltre soglia",
                "size_label": human_bytes(retention_reclaimable),
                "tone": "warning",
                "action": "Retention backup",
                "note": "Recupero governato dalle copie minime configurate.",
            }
        )
    if not recovery_items:
        recovery_items.append(
            {
                "label": "Nessun recupero immediato rilevato",
                "size_label": human_bytes(0),
                "tone": "muted",
                "action": "Monitoraggio",
                "note": "La console continuera' a misurare cache, snapshot e archivi esterni.",
            }
        )

    return {
        "provider_name": provider_name,
        "host_root": str(host_root) if host_root else "",
        "host_iusentra_dir": str(host_iusentra) if host_iusentra else "",
        "connected": bool(host_root or docker.get("available")),
        "disk": {
            "used_bytes": int(host_disk.used),
            "free_bytes": int(host_disk.free),
            "total_bytes": int(host_disk.total),
            "used_label": human_bytes(host_disk.used),
            "free_label": human_bytes(host_disk.free),
            "total_label": human_bytes(host_disk.total),
            "used_percent": round((host_disk.used / host_disk.total) * 100, 1) if host_disk.total else 0,
        },
        "outside_tenants_bytes": outside_tenants,
        "outside_tenants_label": human_bytes(outside_tenants),
        "outside_tenants_note": "Sistema operativo, Docker, codice deploy, backup esterni e dati globali non appartenenti agli studi attivi.",
        "explained_total_bytes": explained_total,
        "explained_total_label": human_bytes(explained_total),
        "outside_breakdown": outside_breakdown,
        "immediate_reclaimable_bytes": immediate_reclaimable,
        "immediate_reclaimable_label": human_bytes(immediate_reclaimable),
        "review_reclaimable_bytes": review_reclaimable,
        "review_reclaimable_label": human_bytes(review_reclaimable),
        "areas": areas,
        "docker": docker,
        "recovery_items": recovery_items,
    }


def build_server_maintenance_surface(config: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = _runtime_config(config)
    data_root = resolve_data_root(cfg)
    backup_dir = resolve_external_backup_dir(cfg)
    disk = shutil.disk_usage(data_root if data_root.exists() else Path("/"))
    scan_settings = storage_scan_settings(cfg)
    registry_available = bool(_registered_tenant_index(data_root, cfg).get("available"))
    all_tenant_rows = _tenant_rows(
        data_root,
        max_files=int(scan_settings["tenant_max_files"]),
        time_budget_seconds=float(scan_settings["tenant_seconds"]),
        config=cfg,
    )
    tenant_rows = [
        row
        for row in all_tenant_rows
        if bool(row.get("active_registered")) or not registry_available
    ]
    inactive_tenant_rows = [
        row
        for row in all_tenant_rows
        if row not in tenant_rows
    ]
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
    backup_retention = run_all_backup_retention(apply=False, config=cfg)
    host_console = build_host_console(
        config=cfg,
        data_root=data_root,
        backup_dir=backup_dir,
        disk=disk,
        tenant_total_size=tenant_total_size,
        backup_external_size=backup_external_size,
    )
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
        recommendations.append("Disco oltre l'80%: liberare cache servizi, snapshot residui e aree non operative.")
    if int(host_console["immediate_reclaimable_bytes"]) > 1024**3:
        recommendations.append(
            "Cache costruzione servizi molto alta: pulirla libera spazio senza toccare dati di studio."
        )
    if int(host_console["review_reclaimable_bytes"]) > 1024**3:
        recommendations.append(
            "Sono presenti aree da verificare fuori dagli studi: controllare snapshot temporanei e retention prima di rimuovere."
        )
    if inactive_tenant_rows:
        recommendations.append(
            f"{len(inactive_tenant_rows)} cartelle dati non sono studi attivi registrati: restano separate dal conteggio operativo."
        )
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
            "tenant_count": len(tenant_rows),
            "tenant_storage_dirs": len(all_tenant_rows),
            "inactive_tenant_dirs": len(inactive_tenant_rows),
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
        "inactive_tenants": inactive_tenant_rows,
        "areas": [area.__dict__ for area in sorted(areas, key=lambda item: item.size_bytes, reverse=True)],
        "host_console": host_console,
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


def _iter_studio_archive_files(data_root: Path, *, tenant_slug: str = "") -> list[Path]:
    roots: list[Path] = []
    slug = str(tenant_slug or "").strip()
    tenants_root = data_root / "tenants"
    if slug:
        roots = [tenants_root / slug]
    elif tenants_root.is_dir():
        roots = [item for item in tenants_root.iterdir() if item.is_dir()]
    else:
        roots = [data_root]

    files: list[Path] = []
    skipped_parts = {"backup", "backups", "dedup_reports", "allegati", "uploads"}
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            lower_parts = {part.lower() for part in path.relative_to(root).parts[:-1]}
            if lower_parts & skipped_parts:
                continue
            if path.suffix.lower() in DB_FILE_SUFFIXES or path.suffix.lower() == ".json":
                files.append(path)
    return sorted(files, key=lambda item: str(item))


def _optimize_json_file(path: Path, *, apply: bool) -> dict[str, Any]:
    before = path.stat().st_size
    try:
        raw = path.read_text(encoding="utf-8")
        payload = json.loads(raw)
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Ottimizzazione JSON non completata per %s: %s", path, exc)
        return {
            "path": str(path),
            "type": "json",
            "optimized": False,
            "before_bytes": before,
            "after_bytes": before,
            "bytes_reclaimable": 0,
            "bytes_reclaimed": 0,
            "error": _public_runtime_error("File JSON non ottimizzabile."),
        }
    compact = (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    reclaimable = max(0, before - len(compact))
    reclaimed = 0
    if apply and reclaimable > 0:
        temp = path.with_name(f".{path.name}.compact-{uuid.uuid4().hex}.tmp")
        try:
            temp.write_bytes(compact)
            os.replace(temp, path)
            reclaimed = reclaimable
        finally:
            try:
                if temp.exists():
                    temp.unlink()
            except OSError:
                pass
    return {
        "path": str(path),
        "type": "json",
        "optimized": bool(reclaimable > 0),
        "before_bytes": before,
        "after_bytes": before - reclaimed if apply else len(compact),
        "bytes_reclaimable": reclaimable,
        "bytes_reclaimed": reclaimed,
        "error": "",
    }


def _optimize_sqlite_file(path: Path, *, apply: bool) -> dict[str, Any]:
    import sqlite3

    before = path.stat().st_size
    try:
        with path.open("rb") as handle:
            if handle.read(16) != b"SQLite format 3\x00":
                return {
                    "path": str(path),
                    "type": "sqlite",
                    "optimized": False,
                    "before_bytes": before,
                    "after_bytes": before,
                    "bytes_reclaimable": 0,
                    "bytes_reclaimed": 0,
                    "error": "Formato SQLite non riconosciuto.",
                }
    except OSError as exc:
        if has_app_context():
            current_app.logger.warning("Lettura SQLite non completata per %s: %s", path, exc)
        return {
            "path": str(path),
            "type": "sqlite",
            "optimized": False,
            "before_bytes": before,
            "after_bytes": before,
            "bytes_reclaimable": 0,
            "bytes_reclaimed": 0,
            "error": _public_runtime_error("Archivio SQLite non leggibile."),
        }

    try:
        if not apply:
            with sqlite3.connect(str(path), timeout=2, isolation_level=None) as conn:
                page_size = int(conn.execute("PRAGMA page_size").fetchone()[0] or 0)
                freelist = int(conn.execute("PRAGMA freelist_count").fetchone()[0] or 0)
            reclaimable = max(0, page_size * freelist)
            return {
                "path": str(path),
                "type": "sqlite",
                "optimized": reclaimable > 0,
                "before_bytes": before,
                "after_bytes": max(0, before - reclaimable),
                "bytes_reclaimable": reclaimable,
                "bytes_reclaimed": 0,
                "error": "",
            }
        with sqlite3.connect(str(path), timeout=5, isolation_level=None) as conn:
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.Error:
                pass
            try:
                conn.execute("PRAGMA optimize")
            except sqlite3.Error:
                pass
            conn.execute("VACUUM")
            try:
                conn.execute("ANALYZE")
            except sqlite3.Error:
                pass
        after = path.stat().st_size
        reclaimed = max(0, before - after)
        return {
            "path": str(path),
            "type": "sqlite",
            "optimized": reclaimed > 0,
            "before_bytes": before,
            "after_bytes": after,
            "bytes_reclaimable": reclaimed,
            "bytes_reclaimed": reclaimed,
            "error": "",
        }
    except sqlite3.Error as exc:
        if has_app_context():
            current_app.logger.warning("Ottimizzazione SQLite non completata per %s: %s", path, exc)
        return {
            "path": str(path),
            "type": "sqlite",
            "optimized": False,
            "before_bytes": before,
            "after_bytes": before,
            "bytes_reclaimable": 0,
            "bytes_reclaimed": 0,
            "error": _public_runtime_error("Archivio SQLite non ottimizzabile."),
        }


def run_database_optimization(
    *,
    apply: bool = False,
    data_root: str | Path | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    root = Path(data_root) if data_root else resolve_data_root()
    files = _iter_studio_archive_files(root, tenant_slug=tenant_slug)
    results: list[dict[str, Any]] = []
    for path in files:
        try:
            if path.suffix.lower() in DB_FILE_SUFFIXES:
                result = _optimize_sqlite_file(path, apply=apply)
            else:
                result = _optimize_json_file(path, apply=apply)
            result["display_path"] = _display_storage_path(str(path.relative_to(root)).replace("\\", "/"))
        except Exception as exc:
            if has_app_context():
                current_app.logger.warning("Ottimizzazione archivio non completata per %s: %s", path, exc)
            result = {
                "path": str(path),
                "display_path": _display_storage_path(str(path)),
                "type": path.suffix.lower().lstrip(".") or "file",
                "optimized": False,
                "before_bytes": 0,
                "after_bytes": 0,
                "bytes_reclaimable": 0,
                "bytes_reclaimed": 0,
                "error": _public_runtime_error("Archivio non ottimizzabile."),
            }
        results.append(result)
    reclaimable = sum(int(item.get("bytes_reclaimable", 0) or 0) for item in results)
    reclaimed = sum(int(item.get("bytes_reclaimed", 0) or 0) for item in results)
    errors = [item for item in results if item.get("error")]
    optimized = [item for item in results if item.get("optimized")]
    return {
        "mock_fallback": False,
        "applied": apply,
        "tenant_slug": str(tenant_slug or "").strip(),
        "files_scanned": len(files),
        "optimized_files": len(optimized),
        "errors_count": len(errors),
        "bytes_reclaimable": reclaimable,
        "bytes_reclaimed": reclaimed,
        "bytes_reclaimable_label": human_bytes(reclaimable),
        "bytes_reclaimed_label": human_bytes(reclaimed),
        "results": sorted(results, key=lambda item: int(item.get("bytes_reclaimable", 0) or 0), reverse=True)[:20],
        "errors": errors[:10],
    }


def _iter_mailbox_databases(data_root: Path, *, tenant_slug: str = "") -> list[Path]:
    slug = str(tenant_slug or "").strip()
    roots: list[Path] = []
    tenants_root = data_root / "tenants"
    if slug:
        roots = [tenants_root / slug]
    elif tenants_root.is_dir():
        roots = [item for item in tenants_root.iterdir() if item.is_dir()]
    else:
        roots = [data_root]

    files: list[Path] = []
    for root in roots:
        email_root = root / "email"
        for name in ("casella.json", "ordinaria.json"):
            path = email_root / name
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda item: str(item))


def run_mail_attachment_archive_compression(
    *,
    apply: bool = False,
    data_root: str | Path | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    from pct.email_client import GestioneEmailRicevute

    root = Path(data_root) if data_root else resolve_data_root()
    files = _iter_mailbox_databases(root, tenant_slug=tenant_slug)
    results: list[dict[str, Any]] = []
    for path in files:
        try:
            gestore = GestioneEmailRicevute(str(path))
            result = gestore.comprimi_allegati(apply=apply)
            result["display_path"] = _display_storage_path(str(path.relative_to(root)).replace("\\", "/"))
        except Exception as exc:
            if has_app_context():
                current_app.logger.warning("Compressione allegati non completata per %s: %s", path, exc)
            result = {
                "mailbox": str(path),
                "display_path": _display_storage_path(str(path)),
                "loose_files": 0,
                "archived_existing": 0,
                "bytes_reclaimable": 0,
                "bytes_reclaimed": 0,
                "error": _public_runtime_error("Allegati non compressi."),
            }
        results.append(result)
    reclaimable = sum(int(item.get("bytes_reclaimable", 0) or 0) for item in results)
    reclaimed = sum(int(item.get("bytes_reclaimed", 0) or 0) for item in results)
    loose_files = sum(int(item.get("loose_files", 0) or 0) for item in results)
    return {
        "mock_fallback": False,
        "applied": apply,
        "tenant_slug": str(tenant_slug or "").strip(),
        "mailboxes_scanned": len(files),
        "loose_files": loose_files,
        "archived_existing": sum(int(item.get("archived_existing", 0) or 0) for item in results),
        "bytes_reclaimable": reclaimable,
        "bytes_reclaimed": reclaimed,
        "bytes_reclaimable_label": human_bytes(reclaimable),
        "bytes_reclaimed_label": human_bytes(reclaimed),
        "results": sorted(results, key=lambda item: int(item.get("bytes_reclaimable", 0) or 0), reverse=True)[:20],
        "errors": [item for item in results if item.get("error")][:10],
    }


def run_max_storage_optimization(
    *,
    apply: bool = False,
    data_root: str | Path | None = None,
    tenant_slug: str = "",
) -> dict[str, Any]:
    root = Path(data_root) if data_root else resolve_data_root()
    compaction = run_storage_compaction(apply=apply, data_root=root, tenant_slug=tenant_slug)
    mail_archives = run_mail_attachment_archive_compression(apply=apply, data_root=root, tenant_slug=tenant_slug)
    databases = run_database_optimization(apply=apply, data_root=root, tenant_slug=tenant_slug)
    reclaimable = int(compaction.get("bytes_reclaimable", 0) or 0) + int(
        databases.get("bytes_reclaimable", 0) or 0
    ) + int(
        mail_archives.get("bytes_reclaimable", 0) or 0
    )
    reclaimed = (
        int(compaction.get("bytes_reclaimed", 0) or 0)
        + int(mail_archives.get("bytes_reclaimed", 0) or 0)
        + int(databases.get("bytes_reclaimed", 0) or 0)
    )
    return {
        "mock_fallback": False,
        "applied": apply,
        "tenant_slug": str(tenant_slug or "").strip(),
        "bytes_reclaimable": reclaimable,
        "bytes_reclaimed": reclaimed,
        "bytes_reclaimable_label": human_bytes(reclaimable),
        "bytes_reclaimed_label": human_bytes(reclaimed),
        "compaction": compaction,
        "mail_archives": mail_archives,
        "databases": databases,
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
        if has_app_context():
            current_app.logger.warning("Avvio backup esterno non completato: %s", exc)
        return {"ok": False, "error": _public_runtime_error("Backup esterno non avviato."), "pid": None}


def run_docker_prune(*, dry_run: bool = True) -> dict[str, Any]:
    """Pulisce solo la cache di costruzione dei servizi, senza toccare volumi dati."""
    before = docker_storage_summary()

    if dry_run:
        reclaimable = int(before.get("build_cache_reclaimable_bytes", 0) or 0)
        return {
            "applied": False,
            "dry_run": True,
            "docker": before,
            "bytes_reclaimable": reclaimable,
            "bytes_reclaimable_label": human_bytes(reclaimable),
            "bytes_reclaimed": 0,
            "bytes_reclaimed_label": human_bytes(0),
            "error": None,
        }
    response = _docker_api_request("POST", "/build/prune?all=1", timeout_seconds=120)
    if response.get("ok"):
        try:
            payload = json.loads(str(response.get("body") or "{}"))
        except json.JSONDecodeError:
            payload = {}
        reclaimed = int(payload.get("SpaceReclaimed", 0) or 0)
        return {
            "applied": True,
            "dry_run": False,
            "stdout": "",
            "error": None,
            "docker": before,
            "bytes_reclaimable": 0,
            "bytes_reclaimable_label": human_bytes(0),
            "bytes_reclaimed": reclaimed,
            "bytes_reclaimed_label": human_bytes(reclaimed),
        }
    try:
        import subprocess

        prune = subprocess.run(
            ["docker", "builder", "prune", "--all", "--force"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        estimated = int(before.get("build_cache_reclaimable_bytes", 0) or 0) if prune.returncode == 0 else 0
        return {
            "applied": prune.returncode == 0,
            "dry_run": False,
            "stdout": prune.stdout,
            "error": prune.stderr if prune.returncode != 0 else None,
            "docker": before,
            "bytes_reclaimable": 0,
            "bytes_reclaimable_label": human_bytes(0),
            "bytes_reclaimed": estimated,
            "bytes_reclaimed_label": human_bytes(estimated),
        }
    except Exception as exc:
        if has_app_context():
            current_app.logger.warning("Pulizia Docker non completata: %s", exc)
        return {
            "applied": False,
            "dry_run": False,
            "docker": before,
            "bytes_reclaimable": 0,
            "bytes_reclaimable_label": human_bytes(0),
            "bytes_reclaimed": 0,
            "bytes_reclaimed_label": human_bytes(0),
            "error": _public_runtime_error("Pulizia Docker non completata."),
        }


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
