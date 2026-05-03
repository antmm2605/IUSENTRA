"""Adapter opzionale Docling per il retrieval documentale Lex.

Il modulo importa Docling solo quando il flag runtime lo richiede: in questo modo
il parser resta attivabile per studi che lo installano localmente, senza rendere
Docling una dipendenza obbligatoria del gestionale.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from .chunking import chunk_structured_text

_TRUE_VALUES = {"1", "true", "yes", "on", "si"}


@dataclass(slots=True)
class DocumentParseChunk:
    document_id: str
    source_hash: str
    chunk_index: int
    text: str
    markdown: str = ""
    page_no: int | None = None
    section_path: str = ""
    bbox_json: str = ""
    table_json: str = ""
    ocr_used: bool = False
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentParseResult:
    document_id: str
    source_path: str
    source_hash: str
    parser: str
    parser_version: str
    markdown: str
    chunks: list[DocumentParseChunk] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    pages: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    json: dict[str, Any] | None = None


class DoclingUnavailableError(RuntimeError):
    """Docling non e' installato o non e' importabile nel runtime corrente."""


def is_docling_enabled(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return str(source.get("LEX_DOCLING_ENABLED", "")).strip().lower() in _TRUE_VALUES


def _docling_version() -> str:
    try:
        return importlib_metadata.version("docling")
    except Exception:
        return "unknown"


def _source_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _jsonable(value: Any) -> Any:
    try:
        return json.loads(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return str(value)


def _first_from_tree(value: Any, keys: set[str]) -> Any | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in keys and item not in (None, "", [], {}):
                return item
        for item in value.values():
            found = _first_from_tree(item, keys)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _first_from_tree(item, keys)
            if found not in (None, "", [], {}):
                return found
    return None


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, parsed))


def _section_path(metadata: dict[str, Any]) -> str:
    value = _first_from_tree(metadata, {"section_path", "headings", "heading", "section", "title"})
    if isinstance(value, (list, tuple)):
        return " > ".join(_clean(item) for item in value if _clean(item))
    return _clean(value)


def _json_fragment(metadata: dict[str, Any], keys: set[str]) -> str:
    value = _first_from_tree(metadata, keys)
    if value in (None, "", [], {}):
        return ""
    try:
        return json.dumps(_jsonable(value), ensure_ascii=False)
    except Exception:
        return _clean(value)


def _bool_from_metadata(metadata: dict[str, Any], *keys: str) -> bool:
    value = _first_from_tree(metadata, {key.lower() for key in keys})
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in _TRUE_VALUES


def _metadata_from_chunk(chunk: Any) -> dict[str, Any]:
    for attr in ("meta", "metadata"):
        value = getattr(chunk, attr, None)
        if value not in (None, "", [], {}):
            return dict(_jsonable(value) or {})
    return {}


def _load_docling_classes() -> tuple[type[Any], type[Any]]:
    try:
        from docling.chunking import HybridChunker
        from docling.document_converter import DocumentConverter
    except Exception as exc:  # pragma: no cover - dipende dall'ambiente runtime
        raise DoclingUnavailableError(f"Docling non disponibile: {exc}") from exc
    return DocumentConverter, HybridChunker


def _build_converter(converter_factory: Callable[[], Any] | None) -> Any:
    if converter_factory is not None:
        return converter_factory()

    DocumentConverter, _HybridChunker = _load_docling_classes()
    if str(os.getenv("LEX_DOCLING_OCR_ENABLED", "")).strip().lower() not in _TRUE_VALUES:
        return DocumentConverter()

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = True
        return DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
    except Exception:
        return DocumentConverter()


def _build_chunker(chunker_factory: Callable[[], Any] | None) -> Any:
    if chunker_factory is not None:
        return chunker_factory()
    _DocumentConverter, HybridChunker = _load_docling_classes()
    return HybridChunker()


def _convert(converter: Any, source: Path) -> Any:
    try:
        return converter.convert(source=source)
    except TypeError:
        return converter.convert(source)


def _export_doc_json(doc: Any) -> dict[str, Any] | None:
    for method_name in ("export_to_dict", "model_dump", "dict"):
        method = getattr(doc, method_name, None)
        if not callable(method):
            continue
        try:
            value = method(mode="json") if method_name == "model_dump" else method()
            if isinstance(value, dict):
                return dict(_jsonable(value) or {})
        except TypeError:
            try:
                value = method()
                if isinstance(value, dict):
                    return dict(_jsonable(value) or {})
            except Exception:
                continue
        except Exception:
            continue
    return None


def _call_table_export(table: Any, method_name: str, doc: Any) -> Any:
    method = getattr(table, method_name, None)
    if not callable(method):
        return None
    for kwargs in ({}, {"doc": doc}):
        try:
            return method(**kwargs)
        except TypeError:
            continue
        except Exception:
            return None
    return None


def _extract_tables(doc: Any) -> list[dict[str, Any]]:
    tables = list(getattr(doc, "tables", []) or [])
    rows: list[dict[str, Any]] = []
    for index, table in enumerate(tables, start=1):
        dataframe = _call_table_export(table, "export_to_dataframe", doc)
        table_json = None
        if dataframe is not None:
            try:
                table_json = json.loads(dataframe.to_json(orient="records", force_ascii=False))
            except Exception:
                table_json = _jsonable(dataframe)
        rows.append(
            {
                "table_index": index,
                "markdown": _clean(_call_table_export(table, "export_to_markdown", doc)),
                "html": _clean(_call_table_export(table, "export_to_html", doc)),
                "rows": table_json,
            }
        )
    return rows


def _extract_pages(doc: Any) -> list[dict[str, Any]]:
    pages = getattr(doc, "pages", None)
    if isinstance(pages, dict):
        return [
            {
                "page_no": _as_int(page_no),
                "metadata": _jsonable(page),
            }
            for page_no, page in pages.items()
        ]
    if isinstance(pages, list):
        return [
            {
                "page_no": index,
                "metadata": _jsonable(page),
            }
            for index, page in enumerate(pages, start=1)
        ]
    return []


def _chunk_text(chunker: Any, chunk: Any) -> str:
    try:
        enriched = chunker.contextualize(chunk=chunk)
    except Exception:
        enriched = ""
    return _clean(enriched or getattr(chunk, "text", ""))


def _extract_chunks(
    *,
    doc: Any,
    markdown: str,
    document_id: str,
    source_hash: str,
    chunker_factory: Callable[[], Any] | None,
    warnings: list[str],
) -> list[DocumentParseChunk]:
    chunks: list[DocumentParseChunk] = []
    try:
        chunker = _build_chunker(chunker_factory)
        chunk_iter = chunker.chunk(dl_doc=doc)
        for index, chunk in enumerate(chunk_iter, start=1):
            metadata = _metadata_from_chunk(chunk)
            text = _chunk_text(chunker, chunk)
            if not text:
                continue
            confidence = _as_float(_first_from_tree(metadata, {"confidence", "score"}), 1.0)
            chunks.append(
                DocumentParseChunk(
                    document_id=document_id,
                    source_hash=source_hash,
                    chunk_index=index,
                    text=text,
                    markdown=text,
                    page_no=_as_int(
                        _first_from_tree(metadata, {"page_no", "page_number", "page", "page_from"})
                    ),
                    section_path=_section_path(metadata),
                    bbox_json=_json_fragment(metadata, {"bbox", "bounding_box", "prov"}),
                    table_json=_json_fragment(metadata, {"table", "table_json"}),
                    ocr_used=_bool_from_metadata(metadata, "ocr_used", "ocr"),
                    confidence=confidence,
                    metadata=metadata,
                )
            )
    except Exception as exc:
        warnings.append(f"Chunking Docling non disponibile: {exc}")

    if chunks:
        return chunks

    for row in chunk_structured_text(markdown):
        text = _clean(row.get("text"))
        if not text:
            continue
        chunks.append(
            DocumentParseChunk(
                document_id=document_id,
                source_hash=source_hash,
                chunk_index=int(row.get("chunk_index") or len(chunks) + 1),
                text=text,
                markdown=_clean(row.get("markdown") or text),
                page_no=_as_int(row.get("page_no")),
                section_path=_clean(row.get("section_path")),
                confidence=_as_float(row.get("confidence"), 0.75),
                metadata=dict(row),
            )
        )
    return chunks


def parse_document_with_docling(
    path: str | Path,
    *,
    document_id: str = "",
    converter_factory: Callable[[], Any] | None = None,
    chunker_factory: Callable[[], Any] | None = None,
) -> DocumentParseResult:
    """Converte un documento locale con Docling e restituisce output citabile."""

    source = Path(path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Documento non trovato: {source}")

    resolved_document_id = _clean(document_id) or source.stem
    source_hash = _source_hash(source)
    parser_version = _docling_version()
    warnings: list[str] = []

    converter = _build_converter(converter_factory)
    conversion = _convert(converter, source)
    doc = getattr(conversion, "document", None)
    if doc is None:
        raise ValueError("Docling non ha restituito un documento convertito.")

    status = _clean(getattr(conversion, "status", ""))
    if status and status.lower() not in {"success", "conversionstatus.success"}:
        warnings.append(f"Stato conversione Docling: {status}")

    try:
        markdown = str(doc.export_to_markdown() or "").strip()
    except Exception as exc:
        markdown = ""
        warnings.append(f"Export Markdown Docling non disponibile: {exc}")

    doc_json = _export_doc_json(doc)
    tables = _extract_tables(doc)
    pages = _extract_pages(doc)
    chunks = _extract_chunks(
        doc=doc,
        markdown=markdown,
        document_id=resolved_document_id,
        source_hash=source_hash,
        chunker_factory=chunker_factory,
        warnings=warnings,
    )

    return DocumentParseResult(
        document_id=resolved_document_id,
        source_path=str(source),
        source_hash=source_hash,
        parser="docling",
        parser_version=parser_version,
        markdown=markdown,
        json=doc_json,
        chunks=chunks,
        tables=tables,
        pages=pages,
        warnings=warnings,
    )
