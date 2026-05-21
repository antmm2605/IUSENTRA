"""Controlli difensivi per archivi ZIP ricevuti via PEC o upload."""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath, PureWindowsPath
from typing import Iterable
from zipfile import ZipInfo

from .mime_detector import SUPPORTED_EXTENSIONS


@dataclass(slots=True)
class ZipSafetyConfig:
    max_single_file_bytes: int = 50 * 1024 * 1024
    max_total_uncompressed_bytes: int = 200 * 1024 * 1024
    max_files: int = 250
    max_depth: int = 3
    max_compression_ratio: float = 120.0
    allowed_extensions: set[str] = field(default_factory=lambda: set(SUPPORTED_EXTENSIONS))


@dataclass(slots=True)
class ZipMemberSafety:
    ok: bool
    status: str
    reason: str
    virtual_path: str

    def to_dict(self) -> dict[str, str | bool]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reason": self.reason,
            "virtual_path": self.virtual_path,
        }


def normalize_virtual_path(name: str) -> str:
    raw = str(name or "").replace("\\", "/")
    raw = re.sub(r"/+", "/", raw).strip("/")
    return posixpath.normpath(raw).replace("\\", "/") if raw else ""


def is_path_traversal(name: str) -> bool:
    raw = str(name or "")
    if not raw.strip():
        return True
    normalized = normalize_virtual_path(raw)
    if normalized in {"", ".", ".."}:
        return True
    if normalized.startswith("../") or "/../" in f"/{normalized}/":
        return True
    if raw.startswith(("/", "\\")):
        return True
    win = PureWindowsPath(raw)
    if win.drive or str(win).startswith("\\\\"):
        return True
    parts = PurePosixPath(normalized).parts
    return any(part in {"", ".", ".."} for part in parts)


def validate_member(
    info: ZipInfo,
    *,
    config: ZipSafetyConfig,
    depth: int,
    running_total: int,
    running_count: int,
    allowed_extensions: Iterable[str] | None = None,
) -> ZipMemberSafety:
    virtual_path = normalize_virtual_path(info.filename)
    if is_path_traversal(info.filename):
        return ZipMemberSafety(False, "unsafe_file", "Percorso interno ZIP non sicuro.", virtual_path)
    if info.is_dir():
        return ZipMemberSafety(True, "directory", "Cartella interna saltata.", virtual_path)
    if depth > config.max_depth:
        return ZipMemberSafety(False, "unsafe_file", "Profondità ZIP annidato oltre il limite configurato.", virtual_path)
    if running_count + 1 > config.max_files:
        return ZipMemberSafety(False, "unsafe_file", "Numero massimo di file estratti superato.", virtual_path)
    if int(info.file_size or 0) > config.max_single_file_bytes:
        return ZipMemberSafety(False, "unsafe_file", "File interno ZIP oltre il limite dimensione singola.", virtual_path)
    if running_total + int(info.file_size or 0) > config.max_total_uncompressed_bytes:
        return ZipMemberSafety(False, "unsafe_file", "Dimensione totale estratta oltre il limite configurato.", virtual_path)
    compressed = max(int(info.compress_size or 0), 1)
    ratio = int(info.file_size or 0) / compressed
    if ratio > config.max_compression_ratio and int(info.file_size or 0) > 1024 * 1024:
        return ZipMemberSafety(False, "unsafe_file", "Rapporto di compressione sospetto: possibile zip bomb.", virtual_path)
    suffixes = [suffix.lower() for suffix in PurePosixPath(virtual_path).suffixes]
    ext = suffixes[-1] if suffixes else ""
    allowed = {str(item).lower() for item in (allowed_extensions or config.allowed_extensions)}
    if ext and ext not in allowed:
        return ZipMemberSafety(False, "quarantined", "Formato interno non ammesso.", virtual_path)
    return ZipMemberSafety(True, "validated", "File interno ZIP validato.", virtual_path)
