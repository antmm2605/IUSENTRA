"""Estrazione testo best-effort per PDF, DOCX e DOC legacy."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from shutil import which
from typing import Any

from .models import DocumentAIPageText


@dataclass(slots=True)
class ExtractionResult:
    ok: bool
    text: str
    pages: list[DocumentAIPageText]
    extraction_engine: str
    warnings: list[str] = field(default_factory=list)
    error_code: str = ""
    error_message: str = ""


@dataclass(slots=True)
class DocumentAITextExtractionResult:
    text: str
    pages: list[DocumentAIPageText]
    extraction_engine: str
    page_count: int | None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def extract_document_text(file_path: str | Path, file_type: str) -> DocumentAITextExtractionResult:
    try:
        content = Path(file_path).read_bytes()
    except OSError as exc:
        return DocumentAITextExtractionResult(
            text="",
            pages=[],
            extraction_engine="read_failed",
            page_count=None,
            warnings=["File non leggibile per l'estrazione testo."],
            error=str(exc),
        )
    result = extract_text_from_document(content, Path(file_path).name, file_type)
    return DocumentAITextExtractionResult(
        text=result.text,
        pages=result.pages,
        extraction_engine=result.extraction_engine,
        page_count=len(result.pages) if result.pages else None,
        warnings=list(result.warnings),
        error=None if result.ok else result.error_message or result.error_code or "Estrazione non completata.",
    )


def extract_text_from_document(content: bytes, filename: str, file_type: str) -> ExtractionResult:
    ext = str(file_type or "").lower().lstrip(".")
    if ext == "pdf":
        return _extract_pdf(content)
    if ext == "docx":
        return _extract_docx(content)
    if ext == "doc":
        return _extract_doc(content)
    return ExtractionResult(
        ok=False,
        text="",
        pages=[],
        extraction_engine="unsupported",
        error_code="unsupported_format",
        error_message="Formato non supportato per l'estrazione testo.",
    )


def _extract_pdf(content: bytes) -> ExtractionResult:
    warnings: list[str] = []
    try:
        import pdfplumber  # type: ignore

        pages: list[DocumentAIPageText] = []
        with pdfplumber.open(BytesIO(content)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append(DocumentAIPageText(page_number=index, text=text))
        full_text = "\n\n".join(page.text for page in pages if page.text)
        if not full_text.strip():
            warnings.append("Il PDF non contiene testo estraibile: potrebbe essere una scansione.")
        return ExtractionResult(
            ok=True,
            text=full_text,
            pages=pages,
            extraction_engine="pdfplumber",
            warnings=warnings,
        )
    except Exception as first_exc:
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(BytesIO(content))
            pages = [
                DocumentAIPageText(page_number=index, text=page.extract_text() or "")
                for index, page in enumerate(reader.pages, start=1)
            ]
            full_text = "\n\n".join(page.text for page in pages if page.text)
            warnings.append("Estrattore PDF primario non disponibile; usato parser alternativo.")
            if not full_text.strip():
                warnings.append("Il PDF non contiene testo estraibile: potrebbe essere una scansione.")
            return ExtractionResult(
                ok=True,
                text=full_text,
                pages=pages,
                extraction_engine="pypdf",
                warnings=warnings,
            )
        except Exception as exc:
            return ExtractionResult(
                ok=False,
                text="",
                pages=[],
                extraction_engine="pdf_failed",
                warnings=["Estrazione PDF non completata."],
                error_code="pdf_extraction_failed",
                error_message=str(exc or first_exc),
            )


def _extract_docx(content: bytes) -> ExtractionResult:
    try:
        from docx import Document  # type: ignore

        document = Document(BytesIO(content))
        chunks: list[str] = []
        for paragraph in document.paragraphs:
            if paragraph.text:
                chunks.append(paragraph.text)
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    chunks.append(" | ".join(cells))
        text = "\n".join(chunks)
        warnings = [] if text.strip() else ["Il DOCX non contiene testo estraibile."]
        return ExtractionResult(ok=True, text=text, pages=[], extraction_engine="python-docx", warnings=warnings)
    except Exception as first_exc:
        try:
            import mammoth  # type: ignore

            result: Any = mammoth.extract_raw_text(BytesIO(content))
            text = str(getattr(result, "value", "") or "")
            warnings = [str(message) for message in getattr(result, "messages", [])]
            return ExtractionResult(ok=True, text=text, pages=[], extraction_engine="mammoth", warnings=warnings)
        except Exception as exc:
            return ExtractionResult(
                ok=False,
                text="",
                pages=[],
                extraction_engine="docx_failed",
                warnings=["Estrazione DOCX non completata."],
                error_code="docx_extraction_failed",
                error_message=str(exc or first_exc),
            )


def _extract_doc(_content: bytes) -> ExtractionResult:
    if which("soffice") or which("libreoffice"):
        return ExtractionResult(
            ok=False,
            text="",
            pages=[],
            extraction_engine="doc_legacy_requires_conversion_adapter",
            warnings=[
                "Estrazione DOC non disponibile nel runtime corrente.",
                "DOC legacy rilevato: conversione LibreOffice non cablata in questa tranche.",
            ],
            error_code="doc_legacy_conversion_not_configured",
            error_message="Formato DOC legacy ammesso in upload ma richiede un adattatore di conversione locale.",
        )
    return ExtractionResult(
        ok=False,
        text="",
        pages=[],
        extraction_engine="doc_legacy_unavailable",
        warnings=["Estrazione DOC non disponibile nel runtime corrente."],
        error_code="doc_legacy_extraction_unavailable",
        error_message="Formato DOC legacy ammesso in upload; estrazione testo non disponibile senza conversione locale.",
    )
