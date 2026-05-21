"""Estrazione sicura e ricorsiva di archivi ZIP con catena padre/figlio."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from .evidence_hash import sha256_bytes
from .mime_detector import MimeDetection, detect_mime
from .zip_safety import ZipSafetyConfig, normalize_virtual_path, validate_member


@dataclass(slots=True)
class ExtractedArchiveFile:
    original_filename: str
    normalized_filename: str
    data: bytes
    mime: MimeDetection
    size: int
    sha256: str
    parent_document_id: str
    root_document_id: str
    root_pec_id: str
    extraction_path_virtuale: str
    extraction_depth: int
    security_status: str
    processing_status: str
    blocked_reason: str = ""
    is_archive: bool = False

    def to_metadata(self) -> dict[str, object]:
        return {
            "original_filename": self.original_filename,
            "normalized_filename": self.normalized_filename,
            "mime_type": self.mime.mime_type,
            "extension": self.mime.extension,
            "size": self.size,
            "sha256": self.sha256,
            "parent_document_id": self.parent_document_id,
            "root_document_id": self.root_document_id,
            "root_pec_id": self.root_pec_id,
            "extraction_path_virtuale": self.extraction_path_virtuale,
            "extraction_depth": self.extraction_depth,
            "security_status": self.security_status,
            "processing_status": self.processing_status,
            "blocked_reason": self.blocked_reason,
            "is_archive": self.is_archive,
        }


@dataclass(slots=True)
class ArchiveExtractionResult:
    files: list[ExtractedArchiveFile] = field(default_factory=list)
    blocked: list[dict[str, object]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_uncompressed: int = 0

    def extend(self, other: "ArchiveExtractionResult") -> None:
        self.files.extend(other.files)
        self.blocked.extend(other.blocked)
        self.warnings.extend(other.warnings)
        self.total_uncompressed += other.total_uncompressed


def extract_zip_bytes(
    data: bytes,
    *,
    filename: str,
    parent_document_id: str,
    root_document_id: str,
    root_pec_id: str = "",
    parent_virtual_path: str = "",
    depth: int = 1,
    config: ZipSafetyConfig | None = None,
) -> ArchiveExtractionResult:
    config = config or ZipSafetyConfig()
    result = ArchiveExtractionResult()
    try:
        archive = ZipFile(io.BytesIO(data))
    except BadZipFile:
        result.blocked.append(
            {
                "filename": filename,
                "security_status": "needs_review",
                "reason": "Archivio ZIP corrotto o non leggibile.",
                "extraction_depth": depth,
            }
        )
        result.warnings.append("Archivio ZIP corrotto o non leggibile.")
        return result

    with archive:
        running_total = 0
        running_count = 0
        used_names: dict[str, int] = {}
        infos = archive.infolist()
        if len([item for item in infos if not item.is_dir()]) > config.max_files:
            result.blocked.append(
                {
                    "filename": filename,
                    "security_status": "unsafe_file",
                    "reason": "Archivio con numero di file oltre il limite configurato.",
                    "count": len(infos),
                    "extraction_depth": depth,
                }
            )
            result.warnings.append("Archivio ZIP bloccato per numero eccessivo di file.")
            return result
        for info in infos:
            safety = validate_member(
                info,
                config=config,
                depth=depth,
                running_total=running_total,
                running_count=running_count,
            )
            virtual_path = _join_virtual(parent_virtual_path, safety.virtual_path)
            if info.is_dir():
                continue
            if not safety.ok:
                result.blocked.append(
                    {
                        "filename": info.filename,
                        "virtual_path": virtual_path,
                        "security_status": safety.status,
                        "reason": safety.reason,
                        "extraction_depth": depth,
                    }
                )
                continue
            try:
                payload = archive.read(info)
            except Exception as exc:
                result.blocked.append(
                    {
                        "filename": info.filename,
                        "virtual_path": virtual_path,
                        "security_status": "needs_review",
                        "reason": f"File interno non leggibile: {exc}",
                        "extraction_depth": depth,
                    }
                )
                continue
            running_total += len(payload)
            running_count += 1
            result.total_uncompressed += len(payload)
            mime = detect_mime(payload, info.filename, allowed_extensions=config.allowed_extensions)
            normalized = _unique_normalized_name(safety.virtual_path, used_names)
            security_status = "validated" if mime.supported else "quarantined"
            processing_status = "extracted" if security_status == "validated" else "needs_review"
            extracted = ExtractedArchiveFile(
                original_filename=str(info.filename),
                normalized_filename=normalized,
                data=payload,
                mime=mime,
                size=len(payload),
                sha256=sha256_bytes(payload),
                parent_document_id=parent_document_id,
                root_document_id=root_document_id,
                root_pec_id=root_pec_id,
                extraction_path_virtuale=virtual_path,
                extraction_depth=depth,
                security_status=security_status,
                processing_status=processing_status,
                blocked_reason="" if mime.supported else "Formato interno non ammesso dalla configurazione.",
                is_archive=mime.mime_type == "application/zip",
            )
            result.files.append(extracted)
            if extracted.is_archive and security_status == "validated":
                if depth >= config.max_depth:
                    result.blocked.append(
                        {
                            "filename": extracted.original_filename,
                            "virtual_path": virtual_path,
                            "security_status": "needs_review",
                            "reason": "ZIP annidato oltre la profondità configurata.",
                            "extraction_depth": depth + 1,
                        }
                    )
                    continue
                nested = extract_zip_bytes(
                    payload,
                    filename=extracted.original_filename,
                    parent_document_id=parent_document_id,
                    root_document_id=root_document_id,
                    root_pec_id=root_pec_id,
                    parent_virtual_path=virtual_path,
                    depth=depth + 1,
                    config=config,
                )
                result.extend(nested)
    return result


def _join_virtual(parent: str, child: str) -> str:
    parent_clean = normalize_virtual_path(parent)
    child_clean = normalize_virtual_path(child)
    if parent_clean and child_clean:
        return f"{parent_clean}/{child_clean}"
    return child_clean or parent_clean


def _unique_normalized_name(virtual_path: str, used_names: dict[str, int]) -> str:
    name = PurePosixPath(normalize_virtual_path(virtual_path)).name or "allegato"
    stem = PurePosixPath(name).stem or "allegato"
    suffix = "".join(PurePosixPath(name).suffixes)
    key = name.casefold()
    count = used_names.get(key, 0)
    used_names[key] = count + 1
    if not count:
        return name
    return f"{stem}-{count + 1}{suffix}"
