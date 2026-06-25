from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from legal_document_ingestion.archive_extractor import extract_zip_bytes
from legal_document_ingestion.evidence_hash import sha256_bytes
from legal_document_ingestion.mime_detector import detect_mime
from legal_document_ingestion.repository import sanitize_filename
from legal_document_ingestion.zip_safety import ZipSafetyConfig
from legal_regex import validate_regex_pack

from .alto import build_alto_xml
from .config import LegalOcrConfig
from .engines import OcrEngine, build_engine
from .models import EngineRun
from .ner_legal import extract_legal_entities
from .postprocess import apply_deterministic_corrections, build_lex_export, build_notification_proposals, build_vector_source_manifest, compute_metrics, suggested_hil_fixes
from .preprocessing import rasterize_document
from .storage import LegalOcrEvidenceStore
from .tables import reconstruct_tables, table_to_csv, table_to_html

SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".zip", ".p7m", ".txt", ".xml", ".json", ".eml"}


class LegalOcrPipeline:
    def __init__(self, config: LegalOcrConfig, store: LegalOcrEvidenceStore, *, engines: dict[str, OcrEngine] | None = None) -> None:
        self.config = config
        self.store = store
        self.engines = engines or {}

    def run_path(self, path: str | Path, *, tenant_id: str | None = None, fascicolo_id: str = "", document_id: str = "", source_type: str = "cli") -> list[dict[str, Any]]:
        target = Path(path)
        if target.is_dir():
            results: list[dict[str, Any]] = []
            for child in sorted(item for item in target.rglob("*") if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES):
                results.extend(self.run_path(child, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id=document_id, source_type=source_type))
            return results
        return self.run_bytes(target.read_bytes(), filename=target.name, tenant_id=tenant_id or self.config.tenant_id, fascicolo_id=fascicolo_id, document_id=document_id, source_type=source_type)

    def run_bytes(self, data: bytes, *, filename: str, tenant_id: str | None = None, fascicolo_id: str = "", document_id: str = "", parent_run_id: str = "", source_type: str = "documento") -> list[dict[str, Any]]:
        clean_filename = filename or "documento.bin"
        mime = detect_mime(data, clean_filename, allowed_extensions=ZipSafetyConfig().allowed_extensions)
        if mime.mime_type == "application/zip" or Path(clean_filename).suffix.lower() == ".zip":
            return self._run_zip(data, filename=clean_filename, tenant_id=tenant_id or self.config.tenant_id, fascicolo_id=fascicolo_id, document_id=document_id, source_type=source_type)
        if Path(clean_filename).suffix.lower() == ".p7m":
            payload = _extract_p7m(data, clean_filename)
            if payload["payload_bytes"]:
                results = self.run_bytes(bytes(payload["payload_bytes"]), filename=str(payload["payload_name"] or clean_filename.removesuffix(".p7m")), tenant_id=tenant_id or self.config.tenant_id, fascicolo_id=fascicolo_id, document_id=document_id, parent_run_id=parent_run_id, source_type=f"{source_type} firmato")
                for result in results:
                    result.setdefault("signed_payload", payload["status"])
                return results
        return [self._run_single(data, filename=clean_filename, tenant_id=tenant_id or self.config.tenant_id, fascicolo_id=fascicolo_id, document_id=document_id, parent_run_id=parent_run_id, source_type=source_type)]

    def _run_zip(self, data: bytes, *, filename: str, tenant_id: str, fascicolo_id: str, document_id: str, source_type: str) -> list[dict[str, Any]]:
        parent_run_id = str(uuid.uuid4())
        self.store.write_raw_blob(parent_run_id, filename, data)
        extraction = extract_zip_bytes(data, filename=filename, parent_document_id=document_id or parent_run_id, root_document_id=document_id or parent_run_id, config=ZipSafetyConfig())
        self.store.append_audit(parent_run_id, "ocr.zip_extracted", {"filename": filename, "files": len(extraction.files), "blocked": extraction.blocked})
        results: list[dict[str, Any]] = []
        for item in extraction.files:
            if item.security_status != "validated" or item.mime.mime_type == "application/zip":
                continue
            results.extend(self.run_bytes(item.data, filename=item.original_filename, tenant_id=tenant_id, fascicolo_id=fascicolo_id, document_id=document_id, parent_run_id=parent_run_id, source_type=f"{source_type} ZIP"))
        return results

    def _run_single(self, data: bytes, *, filename: str, tenant_id: str, fascicolo_id: str, document_id: str, parent_run_id: str, source_type: str) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        ingest_ts = datetime.now(timezone.utc).isoformat()
        raw_blob = self.store.write_raw_blob(run_id, filename, data)
        pages = rasterize_document(data, filename, self.store.pages_dir(run_id))
        primary = self._engine(self.config.primary_engine).run(pages, language=self.config.language)
        selected = primary
        attempts = [_attempt(primary)]
        metrics = compute_metrics(primary.tokens, language_confidence=primary.language_confidence)
        fallback_used = False
        if _requires_fallback(metrics, self.config):
            fallback = self._engine(self.config.fallback_engine).run(pages, language=self.config.language)
            attempts.append(_attempt(fallback))
            fallback_metrics = compute_metrics(fallback.tokens, language_confidence=fallback.language_confidence)
            if _better(fallback_metrics, metrics, fallback, primary):
                selected = fallback
                metrics = fallback_metrics
            fallback_used = True
        corrected, corrections = apply_deterministic_corrections(selected.text, user="system")
        regex_summary = validate_regex_pack(corrected, attempts=len(attempts))
        hil_reasons = _hil_reasons(metrics, regex_summary, self.config)
        text_path = self.store.write_text(run_id, "doc.txt", corrected)
        raw_text_path = self.store.write_text(run_id, "raw.txt", selected.text)
        lex_export = build_lex_export(selected.tokens, min_confidence=self.config.lex_min_confidence)
        lex_export["path"] = self.store.write_text(run_id, "lex.txt", str(lex_export.get("text") or ""))
        vector_source_manifest = build_vector_source_manifest(
            corrected,
            selected.pages_text,
            tenant_id=tenant_id,
            run_id=run_id,
            document_id=document_id,
            fascicolo_id=fascicolo_id,
            engine=selected.engine,
            metrics=metrics,
            hil_required=bool(hil_reasons),
        )
        vector_source_manifest["path"] = self.store.write_text(
            run_id,
            "vector_source_manifest.json",
            json.dumps(vector_source_manifest, ensure_ascii=False, indent=2),
        )
        # Esportazioni strutturate (engine-independent): ALTO-XML, tabelle CSV/HTML, entità legali.
        alto_xml_path = self.store.write_text(run_id, "alto.xml", build_alto_xml(selected.tokens, pages, source_file=filename))
        tables = []
        for index, table in enumerate(reconstruct_tables(selected.tokens), start=1):
            csv_path = self.store.write_text(run_id, f"table_{index}.csv", table_to_csv(table))
            tables.append({"index": index, "page": table.get("page"), "n_rows": table.get("n_rows"), "n_cols": table.get("n_cols"), "csv_path": csv_path, "html": table_to_html(table)})
        legal_entities = extract_legal_entities(corrected)
        self.store.append_audit(run_id, "ocr.structured_export", {"alto_xml_path": alto_xml_path, "tables": len(tables), "legal_entities": legal_entities.get("counts", {})})
        finish_ts = datetime.now(timezone.utc).isoformat()
        evidence = {
            "run_id": run_id,
            "parent_run_id": parent_run_id,
            "tenant_id": tenant_id,
            "document_id": document_id,
            "fascicolo_id": fascicolo_id,
            "source_type": source_type,
            "engine_version": {"primary": primary.version, "fallback": attempts[-1]["version"] if fallback_used else "", "selected": selected.version},
            "selected_engine": selected.engine,
            "fallback_used": fallback_used,
            "raw_blob": raw_blob,
            "pages": [self.store._rel(Path(page.image_path)) for page in pages],
            "ocr_text_path": text_path,
            "raw_text_path": raw_text_path,
            "token_index": selected.tokens,
            "metrics": metrics,
            "regex_summary": regex_summary,
            "correction_history": corrections,
            "suggested_hil_fixes": suggested_hil_fixes(selected.text),
            "qc": {"banding": _banding(metrics), "hil_required": bool(hil_reasons), "hil_reasons": hil_reasons, "fallback_rule": "avg_confidence < 0.85 oppure pct_tokens_<0.75 > 10%", "engine_attempts": attempts},
            "lex_export": lex_export,
            "vector_source_manifest": vector_source_manifest,
            "alto_xml_path": alto_xml_path,
            "tables": tables,
            "legal_entities": legal_entities,
            "notification_proposals": build_notification_proposals(corrected, document_id=document_id, run_id=run_id, fascicolo_id=fascicolo_id),
            "audit": {"ingest_ts": ingest_ts, "finish_ts": finish_ts, "checksums": {"raw": f"sha256:{sha256_bytes(data)}", "pages": [f"sha256:{page.sha256}" for page in pages]}, "worker_id": self.config.worker_id or os.getenv("HOSTNAME") or "iusentra-node", "preprocessing": [asdict(page) for page in pages]},
            "event": {"type": "EvidenceReady", "avg_confidence": metrics["avg_confidence"], "banding": _banding(metrics), "hil_required": bool(hil_reasons), "review_url": f"/documenti/{document_id}/revisione-ocr" if document_id else ""},
        }
        evidence["evidence_path"] = self.store.write_evidence(evidence)
        return evidence

    def _engine(self, name: str) -> OcrEngine:
        if name not in self.engines:
            self.engines[name] = build_engine(name)
        return self.engines[name]


def _attempt(result: EngineRun) -> dict[str, Any]:
    return {"engine": result.engine, "version": result.version, "token_count": len(result.tokens), "warnings": result.warnings, "errors": result.errors}


def _requires_fallback(metrics: dict[str, Any], config: LegalOcrConfig) -> bool:
    return float(metrics.get("avg_confidence") or 0) < config.avg_confidence_fallback_threshold or float(metrics.get("pct_tokens_<0.75") or 0) > config.pct_tokens_low_fallback_threshold


def _better(candidate_metrics: dict[str, Any], current_metrics: dict[str, Any], candidate: EngineRun, current: EngineRun) -> bool:
    if current.errors and not candidate.errors:
        return True
    if candidate.text.strip() and not current.text.strip():
        return True
    if candidate.tokens and not current.tokens:
        return True
    return float(candidate_metrics.get("avg_confidence") or 0) > float(current_metrics.get("avg_confidence") or 0) + 0.02


def _hil_reasons(metrics: dict[str, Any], regex_summary: dict[str, Any], config: LegalOcrConfig) -> list[str]:
    reasons: list[str] = []
    if float(metrics.get("avg_confidence") or 0) < config.avg_confidence_hil_threshold:
        reasons.append("Confidenza media sotto soglia critica.")
    if float(metrics.get("pct_tokens_<0.50") or 0) > config.pct_tokens_very_low_hil_threshold:
        reasons.append("Troppe parole con confidenza molto bassa.")
    if float(((metrics.get("layout_anomalies") or {}).get("missing_bbox_pct")) or 0) > config.layout_missing_bbox_hil_threshold:
        reasons.append("Coordinate di lettura mancanti oltre soglia.")
    for field in regex_summary.get("mandatory_fields") or []:
        if field.get("status") == "fail" and int(field.get("tries") or 1) >= 2:
            reasons.append(f"Campo obbligatorio non validato: {field.get('id')}.")
    return reasons


def _banding(metrics: dict[str, Any]) -> str:
    conf = float(metrics.get("avg_confidence") or 0)
    return "alta" if conf >= 0.90 else "media" if conf >= 0.75 else "bassa"


def _extract_p7m(data: bytes, filename: str) -> dict[str, Any]:
    try:
        from pct.firme_cades import inspect_signed_document_bytes

        result = inspect_signed_document_bytes(source_name=filename, data=data)
        status = asdict(result.status)
        return {"payload_bytes": result.payload_bytes, "payload_name": status.get("payload_name") or sanitize_filename(filename.removesuffix(".p7m")), "status": status}
    except Exception as exc:
        return {"payload_bytes": None, "payload_name": "", "status": {"message": f"P7M non estratto: {exc}"}}
