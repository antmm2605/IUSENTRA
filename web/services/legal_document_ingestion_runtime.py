"""Runtime Flask per Legal Document Understanding e OCR forense."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app, g, has_app_context, has_request_context, session

from legal_document_ingestion import LegalDocumentIngestionService, LegalDocumentRepository
from legal_document_ingestion.file_intake import LegalDocumentIngestionConfig
from legal_document_ingestion.zip_safety import ZipSafetyConfig
from web.helpers import get_fascicoli
from web.services.document_intelligence_runtime import fascicoli_db_path
from web.services.tenant_paths import tenant_data_path


def legal_document_tenant_id() -> str:
    if has_request_context():
        tenant = getattr(g, "tenant", None)
        slug = str(getattr(tenant, "slug", "") or "").strip()
        if slug:
            return slug
        user = g.get("utente_corrente")
        user_slug = str(getattr(user, "tenant_slug", "") or session.get("tenant_slug") or "").strip()
        if user_slug:
            return user_slug
    return "single-studio"


def legal_document_actor() -> str:
    if has_request_context():
        user = g.get("utente_corrente")
        return str(getattr(user, "id", "") or getattr(user, "username", "") or "sistema")
    return "sistema"


def legal_documents_paths() -> tuple[Path, Path]:
    fallback_anchor = Path(fascicoli_db_path()).resolve().parent
    db_default = fallback_anchor / "legal_document_understanding.sqlite"
    storage_default = fallback_anchor / "legal_document_evidence"
    if has_request_context() or has_app_context():
        db_path = Path(
            tenant_data_path(
                "LEGAL_DOCUMENTS_DB",
                str(current_app.config.get("LEGAL_DOCUMENTS_DB") or db_default),
                require_tenant=bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)),
            )
        )
        storage_root = Path(
            tenant_data_path(
                "LEGAL_DOCUMENTS_STORAGE",
                str(current_app.config.get("LEGAL_DOCUMENTS_STORAGE") or storage_default),
                require_tenant=bool(current_app.config.get("MULTI_TENANT") or getattr(g, "multi_tenant_enabled", False)),
            )
        )
        return db_path, storage_root
    return db_default, storage_default


def build_legal_document_repository() -> LegalDocumentRepository:
    db_path, storage_root = legal_documents_paths()
    return LegalDocumentRepository(db_path, storage_root)


def build_legal_document_service() -> LegalDocumentIngestionService:
    config = _config_from_app()
    return LegalDocumentIngestionService(build_legal_document_repository(), get_fascicoli(), config=config)


def _config_from_app() -> LegalDocumentIngestionConfig:
    cfg = current_app.config if has_app_context() else {}
    zip_config = ZipSafetyConfig(
        max_single_file_bytes=int(cfg.get("LEGAL_DOC_ZIP_MAX_SINGLE_FILE_BYTES") or 50 * 1024 * 1024),
        max_total_uncompressed_bytes=int(cfg.get("LEGAL_DOC_ZIP_MAX_TOTAL_BYTES") or 200 * 1024 * 1024),
        max_files=int(cfg.get("LEGAL_DOC_ZIP_MAX_FILES") or 250),
        max_depth=int(cfg.get("LEGAL_DOC_ZIP_MAX_DEPTH") or 3),
        max_compression_ratio=float(cfg.get("LEGAL_DOC_ZIP_MAX_COMPRESSION_RATIO") or 120.0),
    )
    return LegalDocumentIngestionConfig(
        zip_safety=zip_config,
        token_review_threshold=float(cfg.get("LEGAL_DOC_TOKEN_REVIEW_THRESHOLD") or 0.85),
        document_review_threshold=float(cfg.get("LEGAL_DOC_DOCUMENT_REVIEW_THRESHOLD") or 0.78),
        classification_review_threshold=float(cfg.get("LEGAL_DOC_CLASSIFICATION_REVIEW_THRESHOLD") or 0.62),
        enable_forensic_ocr=bool(cfg.get("OCR_FORENSIC_ENABLED", True)),
        enable_archive_extraction=bool(cfg.get("PEC_ZIP_OCR_ENABLED", True)),
        lex_validated_documents_only=bool(cfg.get("LEX_VALIDATED_DOCUMENTS_ONLY", True)),
        language=str(cfg.get("LEGAL_DOC_OCR_LANGUAGE") or "ita"),
    )


def legal_document_user_context() -> dict[str, Any]:
    user = g.get("utente_corrente") if has_request_context() else None
    return {"user": user, "user_id": legal_document_actor(), "tenant_id": legal_document_tenant_id()}


__all__ = [
    "build_legal_document_repository",
    "build_legal_document_service",
    "legal_document_actor",
    "legal_document_tenant_id",
    "legal_document_user_context",
    "legal_documents_paths",
]
