"""Estrazione testo best-effort per documenti leggibili da Lex."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage, Message
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from shutil import which
from typing import Any

from .models import DocumentAIPageText
from .pdf_quality import repair_pdf_cid_placeholders, score_extracted_text_quality


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
    if str(filename or "").strip().lower().endswith(".p7m"):
        payload, payload_name, unwrap_warnings = _unwrap_p7m_payload(content, filename)
        payload_type = _file_type_from_payload(payload, payload_name, fallback=file_type)
        result = extract_text_from_document(payload, payload_name, payload_type)
        result.warnings[:0] = unwrap_warnings
        if result.extraction_engine and not result.extraction_engine.startswith("p7m:"):
            result.extraction_engine = f"p7m:{result.extraction_engine}"
        return result

    ext = str(file_type or "").lower().lstrip(".")
    if ext == "pdf":
        return _extract_pdf(content)
    if ext == "docx":
        return _extract_docx(content)
    if ext == "doc":
        return _extract_doc(content)
    if ext == "txt":
        return _extract_txt(content)
    if ext == "eml":
        return _extract_eml(content)
    return ExtractionResult(
        ok=False,
        text="",
        pages=[],
        extraction_engine="unsupported",
        error_code="unsupported_format",
        error_message="Formato non supportato per l'estrazione testo.",
    )


def _unwrap_p7m_payload(content: bytes, filename: str) -> tuple[bytes, str, list[str]]:
    inner_name = str(filename or "").strip()
    if inner_name.lower().endswith(".p7m"):
        inner_name = inner_name[:-4]
    if _looks_like_pdf(content) and inner_name.lower().endswith(".pdf"):
        return content, inner_name, ["Documento PDF con estensione .p7m letto come PDF interno per l'indice Lex."]
    try:
        from pct.firme_cades import inspect_signed_document_bytes

        signed = inspect_signed_document_bytes(source_name=filename, source_path="", data=content)
        if signed.status.payload_available and signed.payload_bytes:
            payload_name = signed.status.payload_name or inner_name
            return signed.payload_bytes, payload_name, [signed.status.message]
    except Exception:
        pass
    try:
        from pct.firme_cades import (
            extract_signed_payload,
            payload_extension_from_mime,
            payload_mime_from_bytes,
            payload_name_from_source,
        )

        payload = extract_signed_payload(content)
        if payload:
            mime_type = payload_mime_from_bytes(payload, inner_name)
            payload_name = payload_name_from_source(filename, payload_extension_from_mime(mime_type, inner_name))
            return payload, payload_name, ["Contenuto del documento firmato estratto per l'indice Lex."]
    except Exception:
        pass
    return content, inner_name, ["Documento .p7m letto tentando il formato del file interno dichiarato."]


def _file_type_from_payload(content: bytes, filename: str, *, fallback: str) -> str:
    lower_name = str(filename or "").strip().lower()
    for extension in ("pdf", "docx", "doc", "txt", "eml"):
        if lower_name.endswith(f".{extension}"):
            return extension
    if _looks_like_pdf(content):
        return "pdf"
    if content.startswith(b"PK\x03\x04"):
        return "docx"
    return str(fallback or "").lower().lstrip(".")


def _looks_like_pdf(content: bytes) -> bool:
    return bytes(content[:16] if content else b"").lstrip().startswith(b"%PDF")


def _extract_txt(content: bytes) -> ExtractionResult:
    text, encoding, warnings = _decode_text_bytes(content)
    if not text.strip():
        warnings.append("Il file di testo non contiene contenuto leggibile.")
    return ExtractionResult(
        ok=True,
        text=text,
        pages=[],
        extraction_engine=f"text:{encoding}",
        warnings=warnings,
    )


def _decode_text_bytes(content: bytes) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    for encoding in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            text = content.decode(encoding)
            if "\ufffd" in text:
                continue
            if encoding not in {"utf-8-sig", "utf-16"}:
                warnings.append("Testo decodificato con codifica di compatibilità.")
            return _clean_text(text), encoding, warnings
        except UnicodeDecodeError:
            continue
    warnings.append("Testo decodificato sostituendo caratteri non leggibili.")
    return _clean_text(content.decode("utf-8", errors="replace")), "utf-8-replace", warnings


def _clean_text(value: str) -> str:
    return str(value or "").replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []

    def handle_data(self, data: str) -> None:
        clean = " ".join(str(data or "").split())
        if clean:
            self._chunks.append(clean)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"p", "br", "div", "li", "tr", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def text(self) -> str:
        return _clean_text(" ".join(self._chunks))


def _html_to_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    try:
        parser.feed(value)
    except Exception:
        return _clean_text(value)
    return parser.text()


def _extract_eml(content: bytes) -> ExtractionResult:
    try:
        message = BytesParser(policy=policy.default).parsebytes(content)
    except Exception as exc:
        return ExtractionResult(
            ok=False,
            text="",
            pages=[],
            extraction_engine="eml_failed",
            warnings=["L'email non è stata letta."],
            error_code="eml_extraction_failed",
            error_message=str(exc),
        )

    warnings: list[str] = []
    chunks: list[str] = []
    headers = _email_header_lines(message)
    if headers:
        chunks.append("\n".join(headers))

    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachment_chunks: list[str] = []

    for part in message.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        content_type = str(part.get_content_type() or "").lower()
        disposition = str(part.get_content_disposition() or "").lower()
        payload = _email_part_bytes(part)
        if filename or disposition == "attachment":
            attachment_text, attachment_warnings = _extract_eml_attachment(filename or "allegato", payload)
            warnings.extend(attachment_warnings)
            if attachment_text:
                attachment_chunks.append(attachment_text)
            continue
        if content_type == "text/plain":
            text = _email_part_text(part, payload)
            if text.strip():
                plain_parts.append(text)
        elif content_type == "text/html":
            text = _html_to_text(_email_part_text(part, payload))
            if text.strip():
                html_parts.append(text)

    body_parts = plain_parts or html_parts
    if body_parts:
        chunks.append("Corpo email:\n" + "\n\n".join(body_parts))
    if attachment_chunks:
        chunks.append("Allegati leggibili:\n" + "\n\n".join(attachment_chunks))
    if not body_parts and not attachment_chunks:
        warnings.append("Email senza corpo testuale o allegati leggibili.")
    return ExtractionResult(
        ok=True,
        text="\n\n".join(chunk for chunk in chunks if chunk.strip()),
        pages=[],
        extraction_engine="email.message",
        warnings=warnings,
    )


def _email_header_lines(message: Message | EmailMessage) -> list[str]:
    labels = [
        ("Subject", "Oggetto"),
        ("From", "Mittente"),
        ("To", "Destinatari"),
        ("Cc", "Cc"),
        ("Date", "Data"),
    ]
    lines: list[str] = []
    for key, label in labels:
        value = str(message.get(key, "") or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    return lines


def _email_part_bytes(part: Message | EmailMessage) -> bytes:
    payload = part.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload
    raw = part.get_payload()
    if isinstance(raw, str):
        charset = part.get_content_charset() or "utf-8"
        try:
            return raw.encode(charset, errors="replace")
        except LookupError:
            return raw.encode("utf-8", errors="replace")
    if isinstance(raw, list):
        nested: list[bytes] = []
        for item in raw:
            if isinstance(item, Message):
                try:
                    nested.append(item.as_bytes(policy=policy.default))
                except Exception:
                    nested.append(bytes(str(item), "utf-8", errors="replace"))
        return b"\n".join(nested)
    return b""


def _email_part_text(part: Message | EmailMessage, payload: bytes) -> str:
    charset = part.get_content_charset() or "utf-8"
    try:
        return _clean_text(payload.decode(charset))
    except Exception:
        text, _, _warnings = _decode_text_bytes(payload)
        return text


def _extract_eml_attachment(filename: str, payload: bytes) -> tuple[str, list[str]]:
    clean_name = Path(str(filename or "allegato")).name
    if not payload:
        return "", [f"{clean_name}: allegato vuoto o non leggibile."]
    file_type = _file_type_from_payload(payload, clean_name, fallback=Path(clean_name).suffix.lower().lstrip("."))
    if file_type not in {"pdf", "docx", "doc", "txt", "eml"}:
        return "", [f"{clean_name}: allegato non indicizzato perché il formato non è supportato."]
    result = extract_text_from_document(payload, clean_name, file_type)
    warnings = [f"{clean_name}: {warning}" for warning in result.warnings]
    if not result.ok:
        warnings.append(f"{clean_name}: allegato non letto per Lex.")
        return "", warnings
    if not result.text.strip():
        warnings.append(f"{clean_name}: allegato senza testo estraibile.")
        return "", warnings
    return f"[Allegato: {clean_name}]\n{result.text}", warnings


def _extract_pdf(content: bytes) -> ExtractionResult:
    warnings: list[str] = []
    try:
        import pdfplumber  # type: ignore

        pages: list[DocumentAIPageText] = []
        with pdfplumber.open(BytesIO(content)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append(DocumentAIPageText(page_number=index, text=text))
        pages, full_text, repair_warnings = _repair_pdf_text(pages)
        warnings.extend(repair_warnings)
        if not full_text.strip():
            warnings.append("Il PDF non contiene testo estraibile: potrebbe essere una scansione.")
            ocr_result = _extract_scanned_pdf_with_ocr(content, base_warnings=warnings, base_engine="pdfplumber")
            if ocr_result is not None:
                return ocr_result
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
            pages, full_text, repair_warnings = _repair_pdf_text(pages)
            warnings.append("Estrattore PDF primario non disponibile; usato parser alternativo.")
            warnings.extend(repair_warnings)
            if not full_text.strip():
                warnings.append("Il PDF non contiene testo estraibile: potrebbe essere una scansione.")
                ocr_result = _extract_scanned_pdf_with_ocr(content, base_warnings=warnings, base_engine="pypdf")
                if ocr_result is not None:
                    return ocr_result
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


def _extract_scanned_pdf_with_ocr(
    content: bytes,
    *,
    base_warnings: list[str],
    base_engine: str,
) -> ExtractionResult | None:
    try:
        import pypdfium2 as pdfium  # type: ignore
        import pytesseract  # type: ignore
    except Exception as exc:
        base_warnings.append(f"OCR PDF non disponibile: {exc}")
        return None

    tess_config = _configure_tesseract_runtime(pytesseract)
    tesseract_probe = getattr(pytesseract, "get_tesseract_version", None)
    if callable(tesseract_probe):
        try:
            tesseract_probe()
        except Exception as exc:
            base_warnings.append(f"OCR PDF non disponibile: {exc}")
            return None

    lang = _resolve_tesseract_language(
        pytesseract,
        str(os.environ.get("IUSENTRA_DOCUMENT_AI_OCR_LANG") or "ita").strip() or "ita",
        tess_config,
    )
    max_pages = _int_from_env("IUSENTRA_DOCUMENT_AI_OCR_MAX_PAGES", default=0, minimum=0, maximum=1000)
    scale = _float_from_env("IUSENTRA_DOCUMENT_AI_OCR_SCALE", default=2.2, minimum=1.0, maximum=4.0)
    pdf = None
    pages: list[DocumentAIPageText] = []
    warnings = list(base_warnings)
    try:
        pdf = pdfium.PdfDocument(content)
        page_count = len(pdf)
        limit = min(page_count, max_pages) if max_pages else page_count
        if max_pages and page_count > max_pages:
            warnings.append(
                f"OCR limitato a {max_pages} pagine su {page_count}; aumentare "
                "IUSENTRA_DOCUMENT_AI_OCR_MAX_PAGES per indicizzare il documento completo."
            )
        for page_index in range(limit):
            page = None
            bitmap = None
            try:
                page = pdf[page_index]
                bitmap = page.render(scale=scale)
                image = bitmap.to_pil()
                try:
                    text = pytesseract.image_to_string(image, lang=lang, config=tess_config).strip()
                except TypeError:
                    text = pytesseract.image_to_string(image, lang=lang).strip()
            except Exception as exc:
                warnings.append(f"Pagina {page_index + 1}: OCR non completato ({exc}).")
                text = ""
            finally:
                for obj in (bitmap, page):
                    close = getattr(obj, "close", None)
                    if callable(close):
                        try:
                            close()
                        except Exception:
                            pass
            pages.append(DocumentAIPageText(page_number=page_index + 1, text=text))
    except Exception as exc:
        base_warnings.append(f"OCR PDF non completato: {exc}")
        return None
    finally:
        close = getattr(pdf, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass

    full_text = "\n\n".join(page.text for page in pages if page.text)
    if not full_text.strip():
        base_warnings.extend(warning for warning in warnings if warning not in base_warnings)
        base_warnings.append("OCR PDF eseguito ma senza testo leggibile.")
        return None
    warnings.append("PDF senza testo selezionabile: OCR applicato per l'indice Lex.")
    return ExtractionResult(
        ok=True,
        text=full_text,
        pages=pages,
        extraction_engine=f"{base_engine}+ocr",
        warnings=_unique_warnings(warnings),
    )


def _configure_tesseract_runtime(pytesseract: Any) -> str:
    command = _resolve_tesseract_command()
    pytesseract_module = getattr(pytesseract, "pytesseract", None)
    if command and pytesseract_module is not None and hasattr(pytesseract_module, "tesseract_cmd"):
        pytesseract_module.tesseract_cmd = command
    tessdata_dir = _resolve_tessdata_dir(command)
    if tessdata_dir:
        os.environ.setdefault("TESSDATA_PREFIX", tessdata_dir)
        return f"--tessdata-dir {tessdata_dir}"
    return ""


def _resolve_tesseract_command() -> str:
    configured = str(os.environ.get("IUSENTRA_TESSERACT_CMD") or os.environ.get("TESSERACT_CMD") or "").strip()
    if configured and Path(configured).is_file():
        return configured
    discovered = which("tesseract")
    if discovered:
        return discovered
    if os.name == "nt":
        for root in (
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            r"C:\Program Files",
            r"C:\Program Files (x86)",
        ):
            if not root:
                continue
            candidate = Path(root) / "Tesseract-OCR" / "tesseract.exe"
            if candidate.is_file():
                return str(candidate)
    return ""


def _resolve_tessdata_dir(command: str) -> str:
    candidates: list[Path] = []
    for name in ("IUSENTRA_TESSDATA_PREFIX", "TESSDATA_PREFIX"):
        configured = str(os.environ.get(name) or "").strip()
        if configured:
            candidates.append(Path(configured))
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        candidates.append(Path(local_app_data) / "IUSENTRA" / "tessdata")
    if command:
        candidates.append(Path(command).resolve().parent / "tessdata")
    for candidate in candidates:
        if candidate.is_dir() and any(candidate.glob("*.traineddata")):
            return str(candidate)
    return ""


def _resolve_tesseract_language(pytesseract: Any, preferred: str, config: str) -> str:
    requested = [part for part in str(preferred or "ita").split("+") if part]
    get_languages = getattr(pytesseract, "get_languages", None)
    if not callable(get_languages):
        return "+".join(requested) or "ita"
    try:
        available = set(get_languages(config=config))
    except TypeError:
        try:
            available = set(get_languages())
        except Exception:
            return "+".join(requested) or "ita"
    except Exception:
        return "+".join(requested) or "ita"
    selected = [lang for lang in requested if lang in available]
    if selected:
        return "+".join(selected)
    if "ita" in available:
        return "ita"
    if "eng" in available:
        return "eng"
    return "+".join(requested) or "ita"


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


def _repair_pdf_text(pages: list[DocumentAIPageText]) -> tuple[list[DocumentAIPageText], str, list[str]]:
    repaired_pages: list[DocumentAIPageText] = []
    warnings: list[str] = []
    for page in pages:
        repaired, page_warnings = repair_pdf_cid_placeholders(page.text)
        repaired_pages.append(DocumentAIPageText(page_number=page.page_number, text=repaired))
        warnings.extend(page_warnings)
    full_text = "\n\n".join(page.text for page in repaired_pages if page.text)
    original_text = "\n\n".join(page.text for page in pages if page.text)
    original_score = score_extracted_text_quality(original_text)
    repaired_score = score_extracted_text_quality(full_text)
    if repaired_score.score >= original_score.score and warnings:
        return repaired_pages, full_text, _unique_warnings(warnings)
    return pages, original_text, []


def _unique_warnings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        clean = str(value or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _int_from_env(name: str, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _float_from_env(name: str, *, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(str(os.environ.get(name, default)).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))
