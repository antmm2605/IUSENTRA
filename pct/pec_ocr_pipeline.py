"""Compatto orchestratore PEC -> ZIP -> OCR -> Lex per IUSENTRA.

Il modulo non sostituisce la pipeline PEC audit-grade esistente: aggiunge un
percorso end-to-end piccolo e testabile per conservazione WORM, dedup raw blob,
messaggistica topic-first e scheduling OCR.
"""

from __future__ import annotations

import argparse
import email
import json
import re
import shutil
import sqlite3
import stat
import subprocess
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage, Message
from email.utils import parsedate_to_datetime
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from legal_document_ingestion.archive_extractor import extract_zip_bytes
from legal_document_ingestion.evidence_hash import canonical_json, chain_hash, sha256_bytes, utc_now
from legal_document_ingestion.mime_detector import MimeDetection, detect_mime
from legal_document_ingestion.zip_safety import ZipSafetyConfig, normalize_virtual_path


SCHEMA_VERSION = "2026-05-24.pec-ocr-pipeline.v1"
DEFAULT_TENANT_ID = "default"
DEFAULT_MAX_ZIP_BYTES = 250 * 1024 * 1024
DEFAULT_SMALL_FILE_BYTES = 5 * 1024 * 1024
DEFAULT_BATCH_PAGE_THRESHOLD = 100
EICAR_SIGNATURE = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"

BLOCKED_EXTENSIONS = {
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".exe",
    ".hta",
    ".jar",
    ".js",
    ".jse",
    ".lnk",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
    ".wsf",
}

DEFAULT_ALLOWED_EXTENSIONS = {
    ".csv",
    ".docx",
    ".eml",
    ".jpg",
    ".jpeg",
    ".json",
    ".pdf",
    ".png",
    ".pptx",
    ".p7m",
    ".tif",
    ".tiff",
    ".txt",
    ".xlsx",
    ".xml",
    ".zip",
}

OCR_ELIGIBLE_EXTENSIONS = {
    ".csv",
    ".docx",
    ".eml",
    ".jpg",
    ".jpeg",
    ".json",
    ".pdf",
    ".png",
    ".pptx",
    ".tif",
    ".tiff",
    ".txt",
    ".xlsx",
    ".xml",
}


class PecOcrPipelineError(RuntimeError):
    """Errore controllato della pipeline PEC/OCR."""


class WormViolation(PecOcrPipelineError):
    """Tentativo di riscrivere un oggetto WORM con contenuto diverso."""


@dataclass(frozen=True, slots=True)
class PecOcrPipelineConfig:
    runtime_root: Path | str
    tenant_id: str = DEFAULT_TENANT_ID
    max_zip_bytes: int = DEFAULT_MAX_ZIP_BYTES
    small_file_bytes: int = DEFAULT_SMALL_FILE_BYTES
    small_page_threshold: int = 5
    batch_page_threshold: int = DEFAULT_BATCH_PAGE_THRESHOLD
    max_depth: int = 3
    allowed_extensions: set[str] = field(default_factory=lambda: set(DEFAULT_ALLOWED_EXTENSIONS))
    clamscan_path: str = ""
    ocr_engine_name: str = "iusentra-heuristic-ocr"
    actor: str = "pec-ocr-pipeline"


@dataclass(frozen=True, slots=True)
class PipelineMessage:
    topic: str
    payload: dict[str, Any]
    tenant_id: str
    run_id: str
    schema_version: str = SCHEMA_VERSION
    emitted_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "schema_version": self.schema_version,
            "tenant_id": self.tenant_id,
            "run_id": self.run_id,
            "emitted_at": self.emitted_at,
            "payload": self.payload,
        }


@dataclass(frozen=True, slots=True)
class AttachmentCandidate:
    filename: str
    data: bytes
    content_type: str
    virtual_path: str
    depth: int = 0
    source: str = "attachment"


@dataclass(frozen=True, slots=True)
class StoredBlob:
    sha256: str
    stored_path: str
    duplicate: bool
    size: int
    mime: str
    filename: str


class PipelineEventStore:
    """SQLite append-only per eventi e raw blob deduplicati."""

    def __init__(self, db_path: str | Path, raw_root: str | Path, tenant_id: str) -> None:
        self.db_path = Path(db_path)
        self.raw_root = Path(raw_root)
        self.tenant_id = str(tenant_id or DEFAULT_TENANT_ID)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.raw_root.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS raw_blobs (
                    tenant_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    original_filename TEXT NOT NULL,
                    reuse_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, sha256)
                );

                CREATE TABLE IF NOT EXISTS pipeline_events (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL
                );

                CREATE TRIGGER IF NOT EXISTS pipeline_events_no_update
                BEFORE UPDATE ON pipeline_events
                BEGIN
                    SELECT RAISE(ABORT, 'pipeline_events is append-only');
                END;

                CREATE TRIGGER IF NOT EXISTS pipeline_events_no_delete
                BEFORE DELETE ON pipeline_events
                BEGIN
                    SELECT RAISE(ABORT, 'pipeline_events is append-only');
                END;

                CREATE INDEX IF NOT EXISTS idx_pipeline_events_run ON pipeline_events(tenant_id, run_id, occurred_at);
                CREATE INDEX IF NOT EXISTS idx_raw_blobs_tenant ON raw_blobs(tenant_id, updated_at);
                """
            )
            conn.commit()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def put_blob(self, *, filename: str, data: bytes, mime_type: str) -> StoredBlob:
        digest = sha256_bytes(data)
        now = utc_now()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM raw_blobs WHERE tenant_id=? AND sha256=?",
                (self.tenant_id, digest),
            ).fetchone()
            if row:
                conn.execute(
                    """
                    UPDATE raw_blobs
                       SET reuse_count = reuse_count + 1,
                           updated_at = ?
                     WHERE tenant_id = ? AND sha256 = ?
                    """,
                    (now, self.tenant_id, digest),
                )
                conn.commit()
                return StoredBlob(
                    sha256=digest,
                    stored_path=str(row["stored_path"]),
                    duplicate=True,
                    size=int(row["size"] or 0),
                    mime=str(row["mime_type"] or ""),
                    filename=str(row["original_filename"] or filename),
                )

            safe_name = _safe_filename(filename)
            rel = Path("blobs") / "raw" / now[:4] / now[5:7] / digest[:2] / f"{digest}-{safe_name}"
            target = _safe_join(self.raw_root, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            conn.execute(
                """
                INSERT INTO raw_blobs (
                    tenant_id, sha256, stored_path, mime_type, size,
                    original_filename, reuse_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (self.tenant_id, digest, rel.as_posix(), str(mime_type or ""), len(data), filename, now, now),
            )
            conn.commit()
            return StoredBlob(
                sha256=digest,
                stored_path=rel.as_posix(),
                duplicate=False,
                size=len(data),
                mime=str(mime_type or ""),
                filename=filename,
            )

    def append_message(self, message: PipelineMessage, *, actor: str) -> str:
        event = message.to_dict()
        with self.connect() as conn:
            prev = self._latest_event_hash(conn, message.tenant_id)
            entry_hash = chain_hash(prev, event)
            conn.execute(
                """
                INSERT INTO pipeline_events (
                    id, tenant_id, run_id, topic, actor, payload_json,
                    occurred_at, prev_hash, entry_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    message.tenant_id,
                    message.run_id,
                    message.topic,
                    actor,
                    canonical_json(message.payload),
                    message.emitted_at,
                    prev,
                    entry_hash,
                ),
            )
            conn.commit()
        return entry_hash

    def event_rows(self, run_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM pipeline_events
                 WHERE tenant_id=? AND run_id=?
                 ORDER BY occurred_at ASC, rowid ASC
                """,
                (self.tenant_id, run_id),
            ).fetchall()
        return [_row_with_json(row) for row in rows]

    def blob_snapshot(self) -> dict[str, Any]:
        with self.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM raw_blobs WHERE tenant_id=?", (self.tenant_id,)).fetchone()
            reuse = conn.execute(
                "SELECT COALESCE(SUM(reuse_count), 0) AS n FROM raw_blobs WHERE tenant_id=?",
                (self.tenant_id,),
            ).fetchone()
        total_count = int(total["n"] if total else 0)
        reuse_count = int(reuse["n"] if reuse else 0)
        return {
            "raw_blobs": total_count,
            "dedup_reuse_count": reuse_count,
            "dedup_hit_rate": round(reuse_count / max(total_count + reuse_count, 1), 3),
        }

    @staticmethod
    def _latest_event_hash(conn: sqlite3.Connection, tenant_id: str) -> str:
        row = conn.execute(
            """
            SELECT entry_hash
              FROM pipeline_events
             WHERE tenant_id=?
             ORDER BY occurred_at DESC, rowid DESC
             LIMIT 1
            """,
            (tenant_id,),
        ).fetchone()
        return str(row["entry_hash"] or "") if row else ""


class WormStorage:
    """Storage write-once locale, compatibile con il profilo WORM esterno."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_original(
        self,
        *,
        mail_id: str,
        data: bytes,
        received_at: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        digest = sha256_bytes(data)
        date_part = _date_parts(received_at)
        rel = Path("worm") / date_part[0] / date_part[1] / date_part[2] / f"{_safe_stem(mail_id)}.eml"
        target = _safe_join(self.root, rel)
        meta_target = target.with_suffix(target.suffix + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            current = sha256_bytes(target.read_bytes())
            if current != digest:
                raise WormViolation("Oggetto WORM già presente con checksum diverso.")
            return {
                "path": rel.as_posix(),
                "checksum": f"sha256:{digest}",
                "duplicate": True,
                "metadata_path": _relative_to_root(meta_target, self.root),
            }

        with target.open("xb") as handle:
            handle.write(data)
        envelope = {
            "schema_version": SCHEMA_VERSION,
            "mail_id": mail_id,
            "checksum": f"sha256:{digest}",
            "metadata": metadata,
            "created_at": utc_now(),
        }
        with meta_target.open("xb") as handle:
            handle.write(canonical_json(envelope).encode("utf-8"))
        _mark_readonly(target)
        _mark_readonly(meta_target)
        return {
            "path": rel.as_posix(),
            "checksum": f"sha256:{digest}",
            "duplicate": False,
            "metadata_path": _relative_to_root(meta_target, self.root),
        }


class AntivirusScanner:
    """Scanner deterministicamente testabile, con ClamAV opzionale."""

    def __init__(self, clamscan_path: str = "") -> None:
        self.clamscan_path = str(clamscan_path or "").strip()

    def scan(self, data: bytes, *, filename: str) -> dict[str, Any]:
        payload = bytes(data or b"")
        if EICAR_SIGNATURE in payload:
            return {
                "status": "infected",
                "engine": "deterministic-eicar",
                "signature": "EICAR test file",
                "filename": filename,
            }
        if self.clamscan_path:
            return self._scan_with_clamav(payload, filename=filename)
        return {
            "status": "clean",
            "engine": "deterministic-inline",
            "signature": "",
            "filename": filename,
        }

    def _scan_with_clamav(self, data: bytes, *, filename: str) -> dict[str, Any]:
        path = shutil.which(self.clamscan_path) or self.clamscan_path
        with tempfile.TemporaryDirectory(prefix="iusentra-pec-av-") as tmp:
            sample = Path(tmp) / _safe_filename(filename or "sample.bin")
            sample.write_bytes(data)
            completed = subprocess.run(
                [path, "--no-summary", str(sample)],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        if completed.returncode == 0:
            status = "clean"
        elif completed.returncode == 1:
            status = "infected"
        else:
            status = "error"
        return {
            "status": status,
            "engine": "clamav",
            "signature": completed.stdout.strip() or completed.stderr.strip(),
            "filename": filename,
        }


class SignatureValidator:
    """Validazione strutturale delle firme p7m prima dell'estrazione."""

    def validate_message(self, message: Message) -> dict[str, Any]:
        attachments = list(message.iter_attachments())
        signed = [part for part in attachments if _filename(part).lower().endswith(".p7m")]
        results: list[dict[str, Any]] = []
        for part in signed:
            payload = part.get_payload(decode=True) or b""
            ok = _looks_like_pkcs7(payload)
            results.append(
                {
                    "filename": _filename(part),
                    "status": "valid_structural" if ok else "invalid",
                    "method": "pkcs7-structural",
                    "blocking": not ok,
                }
            )
        blocking = any(item["blocking"] for item in results)
        return {
            "status": "invalid" if blocking else "ok" if results else "not_applicable",
            "checked": bool(results),
            "results": results,
        }


class LightweightOcrEngine:
    """OCR leggero e deterministico per test e ambienti senza Tesseract."""

    def __init__(self, engine_name: str = "iusentra-heuristic-ocr") -> None:
        self.engine_name = engine_name

    def run(self, *, data: bytes, filename: str, mime: str, pages: int) -> dict[str, Any]:
        ext = Path(filename).suffix.lower()
        started = utc_now()
        text, engine, errors = self._extract_text(data, filename=filename, mime=mime, ext=ext)
        words = re.findall(r"\w+", text, flags=re.UNICODE)
        avg_conf = 0.94 if text.strip() and not errors else 0.0 if errors else 0.72
        low_conf_pct = 0.0 if avg_conf >= 0.9 else 100.0 if not text.strip() else 18.0
        return {
            "started_at": started,
            "completed_at": utc_now(),
            "engine": engine,
            "ocr_path": "",
            "page_count": int(max(0, pages)),
            "text": text,
            "stats": {
                "avg_conf": round(avg_conf, 3),
                "low_conf_pct": round(low_conf_pct, 2),
                "token_count": len(words),
            },
            "errors": errors,
        }

    def _extract_text(self, data: bytes, *, filename: str, mime: str, ext: str) -> tuple[str, str, list[str]]:
        if ext in {".txt", ".csv", ".json", ".xml", ".eml"} or mime.startswith("text/") or mime in {
            "application/xml",
            "application/json",
            "message/rfc822",
        }:
            return _decode_text(data), "native-text", []
        if ext == ".pdf" or mime == "application/pdf":
            text = _extract_pdf_text_heuristic(data)
            if text:
                return text, "pdf-native-heuristic", []
            return "", self.engine_name, ["PDF senza testo leggibile nel runtime leggero."]
        if ext in {".docx", ".xlsx", ".pptx"}:
            text = _extract_ooxml_text_heuristic(data)
            if text:
                return text, "ooxml-native-heuristic", []
            return "", self.engine_name, ["Documento Office senza testo leggibile nel runtime leggero."]
        if mime.startswith("image/"):
            return "", self.engine_name, ["Immagine da inviare al worker OCR completo."]
        return "", self.engine_name, ["Formato non gestito dal runtime OCR leggero."]


class PecOcrPipeline:
    """Pipeline professionale e compatta per PEC, archivi e OCR."""

    def __init__(
        self,
        config: PecOcrPipelineConfig,
        *,
        scanner: AntivirusScanner | None = None,
        signature_validator: SignatureValidator | None = None,
        ocr_engine: LightweightOcrEngine | None = None,
    ) -> None:
        self.config = config
        self.runtime_root = Path(config.runtime_root)
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.tenant_id = str(config.tenant_id or DEFAULT_TENANT_ID)
        self.worm = WormStorage(self.runtime_root)
        self.store = PipelineEventStore(
            self.runtime_root / "pec_ocr_pipeline.sqlite",
            self.runtime_root,
            self.tenant_id,
        )
        self.scanner = scanner or AntivirusScanner(config.clamscan_path)
        self.signature_validator = signature_validator or SignatureValidator()
        self.ocr_engine = ocr_engine or LightweightOcrEngine(config.ocr_engine_name)
        self.messages: list[PipelineMessage] = []

    def process_eml(
        self,
        raw_eml: bytes,
        *,
        mail_id: str = "",
        priority: str = "high",
        actor: str | None = None,
    ) -> dict[str, Any]:
        run_id = f"run_{uuid.uuid4().hex[:8]}"
        actor = actor or self.config.actor
        raw = bytes(raw_eml or b"")
        if not raw:
            raise PecOcrPipelineError("PEC vuota o non leggibile.")

        message = email.message_from_bytes(raw, policy=policy.default)
        metadata = _message_metadata(message)
        digest = sha256_bytes(raw)
        mail_id = _safe_stem(mail_id or _mail_id(metadata.get("received_at") or "", digest))

        av = self.scanner.scan(raw, filename=f"{mail_id}.eml")
        self._emit(run_id, "mail.security.av", {"mail_id": mail_id, "antivirus": av}, actor=actor)
        if av["status"] != "clean":
            self._emit(
                run_id,
                "mail.quarantine",
                {"mail_id": mail_id, "reason": "antivirus", "antivirus": av, "checksum": f"sha256:{digest}"},
                actor=actor,
            )
            return self._result(run_id, mail_id, "quarantined")

        signature = self.signature_validator.validate_message(message)
        self._emit(run_id, "mail.security.signature", {"mail_id": mail_id, "signature": signature}, actor=actor)
        if signature["status"] == "invalid":
            self._emit(
                run_id,
                "mail.needs_attention",
                {"mail_id": mail_id, "reason": "firma_non_valida", "signature": signature},
                actor=actor,
            )
            return self._result(run_id, mail_id, "needs_attention")

        worm = self.worm.put_original(mail_id=mail_id, data=raw, received_at=metadata["received_at"], metadata=metadata)
        self._emit(
            run_id,
            "mail.ingest",
            {
                "mail_id": mail_id,
                "received_at": metadata["received_at"],
                "sender": metadata["sender"],
                "eml_path": worm["path"],
                "checksum": worm["checksum"],
                "subject": metadata["subject"],
                "worm_duplicate": worm["duplicate"],
            },
            actor=actor,
        )

        candidates = self._collect_attachment_candidates(message, mail_id=mail_id, run_id=run_id, actor=actor)
        unzip_entries: list[dict[str, Any]] = []
        ocr_queue: list[tuple[AttachmentCandidate, MimeDetection, dict[str, Any], int]] = []
        ocr_results: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for candidate in candidates:
            detected = detect_mime(candidate.data, candidate.filename, allowed_extensions=self.config.allowed_extensions)
            member_av = self.scanner.scan(candidate.data, filename=candidate.filename)
            if member_av["status"] != "clean":
                blocked.append(self._block(run_id, candidate, detected, "antivirus", member_av, actor=actor))
                continue
            if _blocked_by_policy(candidate.filename, detected, self.config.allowed_extensions):
                blocked.append(self._block(run_id, candidate, detected, "mime_non_ammesso", {}, actor=actor))
                continue

            pages = estimate_pages(candidate.data, candidate.filename, detected.mime_type)
            stored = self.store.put_blob(filename=candidate.filename, data=candidate.data, mime_type=detected.mime_type)
            entry = {
                "path": _virtual_path(candidate.virtual_path, candidate.filename),
                "mime": detected.mime_type,
                "size": stored.size,
                "checksum": f"sha256:{stored.sha256}",
                "page_est": pages,
                "doc_id": _doc_id(stored.sha256),
                "raw_blob_path": stored.stored_path,
                "dedup": stored.duplicate,
                "depth": candidate.depth,
            }
            unzip_entries.append(entry)
            self._emit(run_id, "raw_blob.stored", {"mail_id": mail_id, **entry}, actor=actor)

            if stored.duplicate:
                self._emit(
                    run_id,
                    "ocr.skipped",
                    {
                        "mail_id": mail_id,
                        "doc_id": entry["doc_id"],
                        "reason": "sha256_gia_presente",
                        "checksum": entry["checksum"],
                    },
                    actor=actor,
                )
                continue
            if not should_ocr(candidate.filename, detected.mime_type):
                continue
            ocr_queue.append((candidate, detected, entry, pages))

        self._emit(
            run_id,
            "mail.unzip",
            {
                "mail_id": mail_id,
                "zip_path": "",
                "entries": unzip_entries,
                "blocked": blocked,
                "limits": {
                    "max_zip_bytes": self.config.max_zip_bytes,
                    "max_depth": self.config.max_depth,
                },
            },
            actor=actor,
        )

        for candidate, detected, entry, pages in ocr_queue:
            task = build_ocr_task(
                entry=entry,
                tenant_id=self.tenant_id,
                priority=priority,
                pages=pages,
                run_id=run_id,
                config=self.config,
            )
            self._emit(run_id, "ocr.task", task, actor=actor)
            ocr = self.ocr_engine.run(data=candidate.data, filename=candidate.filename, mime=detected.mime_type, pages=pages)
            ocr_path = self._write_ocr_result(entry["doc_id"], run_id, ocr)
            result_payload = {
                "doc_id": entry["doc_id"],
                "ocr_path": ocr_path,
                "page_count": ocr["page_count"],
                "engine": ocr["engine"],
                "stats": ocr["stats"],
                "errors": ocr["errors"],
            }
            self._emit(run_id, "ocr.result", result_payload, actor=actor)
            ocr_results.append({"entry": entry, "ocr": result_payload, "text": ocr.get("text") or ""})
            self._emit_indexing_hooks(run_id, mail_id, entry, ocr, metadata, actor=actor)
        has_blocked_event = any(
            message.run_id == run_id and message.topic in {"mail.unzip.blocked", "mail.member.blocked"}
            for message in self.messages
        )
        status = "completed" if not blocked and not has_blocked_event else "needs_attention"
        return self._result(run_id, mail_id, status, ocr_results=ocr_results, blocked=blocked)

    def _collect_attachment_candidates(
        self,
        message: Message,
        *,
        mail_id: str,
        run_id: str,
        actor: str,
    ) -> list[AttachmentCandidate]:
        candidates: list[AttachmentCandidate] = []
        for index, part in enumerate(message.iter_attachments(), start=1):
            filename = _filename(part) or f"allegato-{index}.bin"
            payload = part.get_payload(decode=True) or b""
            content_type = str(part.get_content_type() or "")
            if _is_zip(filename, payload, content_type):
                if len(payload) > self.config.max_zip_bytes:
                    self._emit(
                        run_id,
                        "mail.unzip.blocked",
                        {
                            "mail_id": mail_id,
                            "path": filename,
                            "reason": "Archivio oltre la soglia configurata.",
                            "size": len(payload),
                            "max_zip_bytes": self.config.max_zip_bytes,
                        },
                        actor=actor,
                    )
                    continue
                candidates.extend(self._extract_zip(payload, filename=filename, mail_id=mail_id, run_id=run_id, actor=actor))
            else:
                candidates.append(
                    AttachmentCandidate(
                        filename=filename,
                        data=payload,
                        content_type=content_type,
                        virtual_path=f"/allegati/{normalize_virtual_path(filename)}",
                        depth=0,
                    )
                )
        return candidates

    def _extract_zip(self, data: bytes, *, filename: str, mail_id: str, run_id: str, actor: str) -> list[AttachmentCandidate]:
        zip_config = ZipSafetyConfig(
            max_single_file_bytes=self.config.max_zip_bytes,
            max_total_uncompressed_bytes=self.config.max_zip_bytes,
            max_depth=self.config.max_depth,
            allowed_extensions=set(self.config.allowed_extensions),
        )
        result = extract_zip_bytes(
            data,
            filename=filename,
            parent_document_id=mail_id,
            root_document_id=mail_id,
            root_pec_id=mail_id,
            parent_virtual_path=f"/allegati/{normalize_virtual_path(filename)}",
            depth=1,
            config=zip_config,
        )
        for item in result.blocked:
            self._emit(run_id, "mail.unzip.blocked", {"mail_id": mail_id, **dict(item)}, actor=actor)
        candidates: list[AttachmentCandidate] = []
        for item in result.files:
            if item.security_status != "validated":
                self._emit(
                    run_id,
                    "mail.unzip.blocked",
                    {
                        "mail_id": mail_id,
                        "path": item.extraction_path_virtuale,
                        "reason": item.blocked_reason or "Formato interno non ammesso.",
                        "security_status": item.security_status,
                    },
                    actor=actor,
                )
                continue
            if item.is_archive:
                continue
            candidates.append(
                AttachmentCandidate(
                    filename=item.normalized_filename,
                    data=item.data,
                    content_type=item.mime.mime_type,
                    virtual_path=f"/{item.extraction_path_virtuale.strip('/')}",
                    depth=item.extraction_depth,
                    source="zip_member",
                )
            )
        return candidates

    def _block(
        self,
        run_id: str,
        candidate: AttachmentCandidate,
        detected: MimeDetection,
        reason: str,
        details: dict[str, Any],
        *,
        actor: str,
    ) -> dict[str, Any]:
        payload = {
            "path": _virtual_path(candidate.virtual_path, candidate.filename),
            "filename": candidate.filename,
            "mime": detected.mime_type,
            "size": len(candidate.data),
            "checksum": f"sha256:{sha256_bytes(candidate.data)}",
            "reason": reason,
            "details": details,
        }
        self._emit(run_id, "mail.member.blocked", payload, actor=actor)
        return payload

    def _write_ocr_result(self, doc_id: str, run_id: str, ocr: dict[str, Any]) -> str:
        rel = Path("blobs") / "ocr" / utc_now()[:4] / utc_now()[5:7] / f"{doc_id}-{run_id}.jsonl"
        target = _safe_join(self.runtime_root, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        line = canonical_json(
            {
                "schema_version": SCHEMA_VERSION,
                "doc_id": doc_id,
                "run_id": run_id,
                "ocr": ocr,
            }
        )
        target.write_text(line + "\n", encoding="utf-8")
        return rel.as_posix()

    def _emit_indexing_hooks(
        self,
        run_id: str,
        mail_id: str,
        entry: dict[str, Any],
        ocr: dict[str, Any],
        metadata: dict[str, Any],
        *,
        actor: str,
    ) -> None:
        text = str(ocr.get("text") or "")
        fascicolo = infer_fascicolo_candidate(" ".join([entry.get("path", ""), text, metadata.get("subject", "")]))
        index_payload = {
            "doc_id": entry["doc_id"],
            "mail_id": mail_id,
            "checksum": entry["checksum"],
            "fascicolo_candidate": fascicolo,
            "text_chars": len(text),
            "avg_conf": (ocr.get("stats") or {}).get("avg_conf", 0),
            "needs_attention": bool(ocr.get("errors")),
        }
        self._emit(run_id, "document.indexed", index_payload, actor=actor)
        self._emit(
            run_id,
            "lex.ingest.doc",
            {
                **index_payload,
                "citations": [
                    {
                        "type": "pec_attachment",
                        "mail_id": mail_id,
                        "doc_id": entry["doc_id"],
                        "checksum": entry["checksum"],
                    }
                ],
                "audit": {
                    "run_id": run_id,
                    "schema_version": SCHEMA_VERSION,
                },
            },
            actor=actor,
        )

    def _emit(self, run_id: str, topic: str, payload: dict[str, Any], *, actor: str) -> PipelineMessage:
        message = PipelineMessage(topic=topic, payload=payload, tenant_id=self.tenant_id, run_id=run_id)
        self.messages.append(message)
        self.store.append_message(message, actor=actor)
        return message

    def _result(
        self,
        run_id: str,
        mail_id: str,
        status: str,
        *,
        ocr_results: list[dict[str, Any]] | None = None,
        blocked: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        events = [message.to_dict() for message in self.messages if message.run_id == run_id]
        return {
            "ok": status == "completed",
            "status": status,
            "tenant_id": self.tenant_id,
            "run_id": run_id,
            "mail_id": mail_id,
            "events": events,
            "events_by_topic": dict(Counter(message["topic"] for message in events)),
            "ocr_results": ocr_results or [],
            "blocked": blocked or [],
            "health": pipeline_health(events, self.store.blob_snapshot()),
        }


def build_ocr_task(
    *,
    entry: dict[str, Any],
    tenant_id: str,
    priority: str,
    pages: int,
    run_id: str,
    config: PecOcrPipelineConfig,
) -> dict[str, Any]:
    size = int(entry.get("size") or 0)
    schedule = schedule_policy(size=size, pages=pages, priority=priority, config=config)
    return {
        "doc_id": entry["doc_id"],
        "source_path": entry["raw_blob_path"],
        "mime": entry["mime"],
        "pages": pages,
        "priority": priority,
        "tenant_id": tenant_id,
        "retry_policy": {"max_attempts": 5, "backoff": "exponential", "base_seconds": 10},
        "run_id": run_id,
        "schedule": schedule,
    }


def schedule_policy(*, size: int, pages: int, priority: str, config: PecOcrPipelineConfig) -> dict[str, Any]:
    if size < config.small_file_bytes or pages < config.small_page_threshold:
        mode = "immediate"
    elif pages > config.batch_page_threshold:
        mode = "batch_window"
    else:
        mode = "tenant_fifo"
    concurrency = 1 if priority == "high" else 2
    return {
        "mode": mode,
        "small_first": mode == "immediate",
        "fifo_scope": "sender+tenant" if priority == "high" else "tenant",
        "tenant_concurrency": concurrency,
        "sla_seconds": 300 if priority == "high" and mode == "immediate" else 3600,
    }


def should_ocr(filename: str, mime_type: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in OCR_ELIGIBLE_EXTENSIONS or mime_type.startswith("image/") or mime_type in {
        "application/pdf",
        "application/xml",
        "text/plain",
        "message/rfc822",
    }


def estimate_pages(data: bytes, filename: str, mime_type: str) -> int:
    ext = Path(filename).suffix.lower()
    raw = bytes(data or b"")
    if mime_type == "application/pdf" or ext == ".pdf":
        markers = len(re.findall(rb"/Type\s*/Page\b", raw))
        return max(1, markers)
    if mime_type.startswith("image/") or ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}:
        return 1
    if ext in {".docx", ".xlsx", ".pptx"}:
        return max(1, min(1000, len(raw) // 50000 + 1))
    chars = len(_decode_text(raw))
    return max(1, chars // 4000 + (1 if chars % 4000 else 0))


def infer_fascicolo_candidate(text: str) -> dict[str, Any]:
    source = str(text or "")
    match = re.search(r"\bR\.?\s*G\.?\s*(?:n\.?\s*)?([0-9]{1,7})\s*/\s*(20[0-9]{2})\b", source, re.IGNORECASE)
    if not match:
        return {"status": "needs_reconciliation", "confidence": 0.0, "rg": "", "anno": ""}
    return {
        "status": "candidate",
        "confidence": 0.82,
        "rg": match.group(1),
        "anno": match.group(2),
        "reason": "Numero R.G. letto nel nome file, corpo PEC o testo OCR.",
    }


def pipeline_health(events: list[dict[str, Any]], blob_snapshot: dict[str, Any]) -> dict[str, Any]:
    ocr_results = [event for event in events if event["topic"] == "ocr.result"]
    failed = [event for event in ocr_results if (event.get("payload") or {}).get("errors")]
    avg_conf_values = [
        float((((event.get("payload") or {}).get("stats") or {}).get("avg_conf") or 0))
        for event in ocr_results
    ]
    avg_conf = round(sum(avg_conf_values) / len(avg_conf_values), 3) if avg_conf_values else 0.0
    return {
        "ocr_success_pct": round(100.0 * (len(ocr_results) - len(failed)) / max(len(ocr_results), 1), 2),
        "ocr_avg_conf": avg_conf,
        "dedup_hit_rate": blob_snapshot.get("dedup_hit_rate", 0),
        "raw_blobs": blob_snapshot.get("raw_blobs", 0),
        "needs_attention": len([event for event in events if event["topic"].endswith("blocked") or event["topic"] == "mail.needs_attention"]),
        "queue_depth": len([event for event in events if event["topic"] == "ocr.task"]) - len(ocr_results),
    }


def build_demo_eml(zip_payload: bytes, *, sender: str = "cancelleria@pec.giustizia.it") -> bytes:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = "studio@example.pec.it"
    message["Subject"] = "POSTA CERTIFICATA: deposito atti R.G. 1234/2026"
    message["Date"] = "Sat, 23 May 2026 10:21:15 +0000"
    message["Message-ID"] = f"<{uuid.uuid4().hex}@iusentra.test>"
    message.set_content(
        "Comunicazione di cancelleria con allegati per R.G. 1234/2026. "
        "Il fascicolo va riconciliato prima di assumere termini conclusivi."
    )
    message.add_attachment(zip_payload, maintype="application", subtype="zip", filename="allegati.zip")
    return message.as_bytes(policy=policy.default)


def run_demo(runtime_root: str | Path) -> dict[str, Any]:
    from io import BytesIO
    from zipfile import ZIP_DEFLATED, ZipFile

    bio = BytesIO()
    with ZipFile(bio, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "allegati/ricorso.txt",
            "Tribunale di Milano\nRicorso R.G. 1234/2026\nUdienza fissata al 10/10/2026.",
        )
        archive.writestr("allegati/copia-ricorso.txt", "Tribunale di Milano\nRicorso R.G. 1234/2026\nUdienza fissata al 10/10/2026.")
        archive.writestr("ricevute/daticert.xml", "<?xml version='1.0'?><postacert><tipo>avvenuta_consegna</tipo></postacert>")
    pipeline = PecOcrPipeline(PecOcrPipelineConfig(runtime_root=runtime_root, tenant_id="studio_legale_pct"))
    return pipeline.process_eml(build_demo_eml(bio.getvalue()), priority="high")


def _message_metadata(message: Message) -> dict[str, str]:
    return {
        "sender": str(message.get("From") or ""),
        "subject": str(message.get("Subject") or ""),
        "received_at": _parsed_date(str(message.get("Date") or "")) or utc_now(),
        "message_id": str(message.get("Message-ID") or ""),
    }


def _parsed_date(value: str) -> str:
    try:
        parsed = parsedate_to_datetime(str(value or ""))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def _mail_id(received_at: str, digest: str) -> str:
    date_part = str(received_at or utc_now())[:10].replace("-", "")
    return f"pec_{date_part}_{digest[:12]}"


def _date_parts(received_at: str) -> tuple[str, str, str]:
    source = str(received_at or utc_now())
    try:
        parsed = datetime.fromisoformat(source.replace("Z", "+00:00"))
    except ValueError:
        parsed = datetime.now(timezone.utc)
    return f"{parsed.year:04d}", f"{parsed.month:02d}", f"{parsed.day:02d}"


def _filename(part: Message) -> str:
    return str(part.get_filename() or "").replace("\\", "/").split("/")[-1]


def _is_zip(filename: str, data: bytes, content_type: str = "") -> bool:
    return (
        Path(filename).suffix.lower() == ".zip"
        or str(content_type or "").lower() == "application/zip"
        or bytes(data or b"").startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    )


def _looks_like_pkcs7(data: bytes) -> bool:
    raw = bytes(data or b"").lstrip()
    return raw.startswith((b"-----BEGIN PKCS7", b"-----BEGIN CMS", b"\x30\x80", b"\x30\x82"))


def _blocked_by_policy(filename: str, detected: MimeDetection, allowed_extensions: Iterable[str]) -> bool:
    ext = Path(filename).suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        return True
    allowed = {str(item).lower() for item in allowed_extensions}
    if ext and ext not in allowed:
        return True
    return not detected.supported


def _virtual_path(path: str, filename: str) -> str:
    clean = normalize_virtual_path(path)
    if clean:
        return f"/{clean.strip('/')}"
    return f"/allegati/{normalize_virtual_path(filename)}"


def _doc_id(sha256: str) -> str:
    return f"doc_{str(sha256 or '')[:12]}"


def _safe_filename(filename: str) -> str:
    raw = PurePosixPath(str(filename or "documento.bin").replace("\\", "/")).name
    raw = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("._-")
    if not raw:
        raw = "documento.bin"
    return raw[:140]


def _safe_stem(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "pec")).strip("._-")
    return clean[:120] or "pec"


def _safe_join(root: Path, rel: Path) -> Path:
    root = root.resolve()
    target = (root / rel).resolve()
    if root != target and root not in target.parents:
        raise PecOcrPipelineError("Percorso di storage non sicuro.")
    return target


def _relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def _mark_readonly(path: Path) -> None:
    try:
        path.chmod(stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
    except OSError:
        pass


def _decode_text(data: bytes) -> str:
    raw = bytes(data or b"")
    for encoding in ("utf-8", "windows-1252", "iso-8859-1"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def _extract_pdf_text_heuristic(data: bytes) -> str:
    text = _decode_text(data)
    text = re.sub(r"%PDF-[^\n]*", " ", text)
    text = re.sub(r"\b(obj|endobj|stream|endstream|xref|trailer)\b", " ", text)
    text = re.sub(r"[^A-Za-z0-9À-ÿ.,;:!?/()\s-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_ooxml_text_heuristic(data: bytes) -> str:
    try:
        from io import BytesIO
        from zipfile import ZipFile

        parts: list[str] = []
        with ZipFile(BytesIO(data)) as archive:
            for name in archive.namelist():
                if name.startswith(("word/", "xl/sharedStrings", "ppt/slides/")) and name.endswith(".xml"):
                    parts.append(_decode_text(archive.read(name)))
        joined = re.sub(r"<[^>]+>", " ", " ".join(parts))
        return re.sub(r"\s+", " ", joined).strip()
    except Exception:
        return ""


def _row_with_json(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    if "payload_json" in payload:
        try:
            payload["payload"] = json.loads(payload["payload_json"] or "{}")
        except json.JSONDecodeError:
            payload["payload"] = {}
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Esegue il test veritiero della pipeline PEC -> OCR IUSENTRA.")
    parser.add_argument("--runtime-root", default="", help="Cartella runtime temporanea o persistente.")
    args = parser.parse_args(argv)
    if args.runtime_root:
        result = run_demo(args.runtime_root)
    else:
        with tempfile.TemporaryDirectory(prefix="iusentra-pec-ocr-") as tmp:
            result = run_demo(tmp)
    compact = {
        "ok": result["ok"],
        "status": result["status"],
        "mail_id": result["mail_id"],
        "run_id": result["run_id"],
        "events_by_topic": result["events_by_topic"],
        "health": result["health"],
        "ocr_results": [
            {
                "doc_id": item["entry"]["doc_id"],
                "path": item["entry"]["path"],
                "avg_conf": item["ocr"]["stats"]["avg_conf"],
                "errors": item["ocr"]["errors"],
            }
            for item in result["ocr_results"]
        ],
    }
    print(canonical_json(compact))
    return 0 if result["ok"] and compact["ocr_results"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
