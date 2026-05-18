"""Genera corpus Lex/RAG dalle evidenze web verificate nel DB fonti.

Non naviga il web e non chiama LLM: usa solo `web_verification_evidence` gia'
popolata dal percorso fonte ufficiale -> allegato -> estrazione/OCR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from lex.dataset.chunking import ChunkingOptions, chunk_documents
from lex.dataset.models import DocumentPage, StudioDatasetDocument, stable_id
from lex.memory_tree import build_and_write_lex_memory_tree
from pct.legal_update_enrichment import (
    build_contextual_question_matrix,
    extract_legal_references,
    legal_reference_labels,
)


DEFAULT_TENANT_ID = "legal-sources"
DEFAULT_OUTPUT_DIR = Path("tmp") / "lex-source-corpus"
CASSAZIONE_DOCUMENT_URL_MARKERS = (
    "/it/civile_dettaglio.page",
    "/it/penale_dettaglio.page",
    "/it/qsp_dettaglio.page",
    "/it/qsc_dettaglio.page",
    "/it/quc_dettaglio.page",
    "/it/rlc_dettaglio.page",
    "/it/rlp_dettaglio.page",
    "/it/su_dettaglio.page",
)
CASSAZIONE_DOCUMENT_SOURCE_CODES = {
    "cassazione_massimario",
    "cassazione_ultime_sent_ord_questioni",
}
RG_REFERENCE_RE = re.compile(r"\bR\.?\s*G\.?(?:\s*n\.?)?\s*([0-9]{1,6}/[0-9]{4})\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class SourceCorpusOptions:
    intelligence_db: Path
    output_dir: Path
    tenant_id: str = DEFAULT_TENANT_ID
    limit: int = 1000
    statuses: tuple[str, ...] = ("verified",)
    source_codes: tuple[str, ...] = ()
    review_ids: tuple[int, ...] = ()
    min_context_chars: int = 1
    max_chars: int = 1200
    overlap_chars: int = 120
    overwrite: bool = False


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea corpus RAG Lex da evidenze web ufficiali gia' verificate nel DB."
    )
    parser.add_argument("--intelligence-db", default="data/intelligence/legal_updates.db")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--tenant-id", default=DEFAULT_TENANT_ID)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--status", action="append", default=[])
    parser.add_argument("--source-code", action="append", default=[])
    parser.add_argument("--review-id", action="append", type=int, default=[])
    parser.add_argument("--include-insufficient", action="store_true")
    parser.add_argument("--min-context-chars", type=int, default=1)
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap-chars", type=int, default=120)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    statuses = tuple(args.status or ("verified",))
    if args.include_insufficient and "insufficient" not in statuses:
        statuses = (*statuses, "insufficient")
    result = generate_source_corpus(
        SourceCorpusOptions(
            intelligence_db=Path(args.intelligence_db),
            output_dir=Path(args.output_dir),
            tenant_id=str(args.tenant_id or DEFAULT_TENANT_ID),
            limit=max(1, int(args.limit or 1)),
            statuses=tuple(str(item or "").strip().lower() for item in statuses if str(item or "").strip()),
            source_codes=tuple(str(item or "").strip().lower() for item in args.source_code or [] if str(item or "").strip()),
            review_ids=tuple(int(item) for item in args.review_id or [] if int(item or 0) > 0),
            min_context_chars=max(0, int(args.min_context_chars or 0)),
            max_chars=max(120, int(args.max_chars or 1200)),
            overlap_chars=max(0, int(args.overlap_chars or 120)),
            overwrite=bool(args.overwrite),
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


def generate_source_corpus(options: SourceCorpusOptions) -> dict[str, Any]:
    if not options.intelligence_db.exists():
        raise FileNotFoundError(f"Database fonti non trovato: {options.intelligence_db}")
    _prepare_output_dir(options.output_dir, overwrite=options.overwrite)
    rows = _load_evidence_rows(options)
    documents = [_document_from_evidence(row, tenant_id=options.tenant_id) for row in rows]
    chunks = chunk_documents(
        documents,
        options=ChunkingOptions(
            max_chars=options.max_chars,
            overlap_chars=options.overlap_chars,
            min_chars=40,
        ),
    )

    options.output_dir.mkdir(parents=True, exist_ok=True)
    document_ai_path = options.output_dir / "documenti_ai" / "documenti_ai.json"
    document_ai_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(options.output_dir / "manifest.json", _manifest(options, rows, documents, chunks, document_ai_path))
    _write_jsonl(options.output_dir / "documents.jsonl", [document.to_dict() for document in documents])
    _write_jsonl(options.output_dir / "chunks.jsonl", [chunk.to_dict(include_text=True) for chunk in chunks])
    _write_jsonl(options.output_dir / "expected_queries.jsonl", [_expected_query(row) for row in rows])
    _write_json(document_ai_path, _document_ai_payload(documents, rows))
    memory_tree = build_and_write_lex_memory_tree(
        documents,
        options.output_dir,
        max_chars=max(options.max_chars, 1800),
        overlap_chars=min(options.overlap_chars, max(0, max(options.max_chars, 1800) - 1)),
    )

    return {
        "ok": True,
        "intelligence_db": str(options.intelligence_db),
        "output_dir": str(options.output_dir),
        "tenant_id": options.tenant_id,
        "documents_count": len(documents),
        "chunks_count": len(chunks),
        "statuses": list(options.statuses),
        "document_ai_json": str(document_ai_path),
        "manifest": str(options.output_dir / "manifest.json"),
        "documents_jsonl": str(options.output_dir / "documents.jsonl"),
        "chunks_jsonl": str(options.output_dir / "chunks.jsonl"),
        "expected_queries_jsonl": str(options.output_dir / "expected_queries.jsonl"),
        "memory_tree": memory_tree,
    }


def _load_evidence_rows(options: SourceCorpusOptions) -> list[dict[str, Any]]:
    clauses = [
        "COALESCE(e.content_text, '') <> ''",
        "COALESCE(e.context_chars, 0) >= ?",
    ]
    params: list[Any] = [int(options.min_context_chars)]
    statuses = tuple(status for status in options.statuses if status)
    if statuses:
        clauses.append("LOWER(COALESCE(e.verification_status, '')) IN ({})".format(",".join("?" for _ in statuses)))
        params.extend(statuses)
    if options.source_codes:
        clauses.append("LOWER(COALESCE(e.source_code, '')) IN ({})".format(",".join("?" for _ in options.source_codes)))
        params.extend(options.source_codes)
        cassazione_document_sources = tuple(
            code for code in options.source_codes if code in CASSAZIONE_DOCUMENT_SOURCE_CODES
        )
        if cassazione_document_sources:
            source_placeholders = ",".join("?" for _ in cassazione_document_sources)
            url_haystack = (
                "LOWER(COALESCE(e.source_url, '') || ' ' || "
                "COALESCE(e.attachment_url, '') || ' ' || COALESCE(r.source_url, ''))"
            )
            clauses.append(
                f"(LOWER(COALESCE(e.source_code, '')) NOT IN ({source_placeholders})"
                " OR "
                + " OR ".join(f"{url_haystack} LIKE ?" for _ in CASSAZIONE_DOCUMENT_URL_MARKERS)
                + ")"
            )
            params.extend(cassazione_document_sources)
            params.extend(f"%{marker}%" for marker in CASSAZIONE_DOCUMENT_URL_MARKERS)
    if options.review_ids:
        clauses.append("COALESCE(e.review_id, 0) IN ({})".format(",".join("?" for _ in options.review_ids)))
        params.extend(int(item) for item in options.review_ids)
    params.append(int(options.limit))

    with sqlite3.connect(str(options.intelligence_db)) as conn:
        conn.row_factory = sqlite3.Row
        _assert_evidence_table(conn)
        rows = conn.execute(
            f"""
            SELECT e.*,
                   n.title AS normalized_title,
                   n.attachments_json AS normalized_attachments_json,
                   r.source_url AS raw_source_url,
                   s.name AS db_source_name
            FROM web_verification_evidence e
            LEFT JOIN source_documents_normalized n ON n.id = e.normalized_document_id
            LEFT JOIN source_documents_raw r ON r.id = n.raw_document_id
            LEFT JOIN sources s ON s.code = e.source_code
            WHERE {' AND '.join(clauses)}
            ORDER BY e.is_official DESC, e.context_chars DESC, e.updated_at DESC, e.id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [dict(row) for row in rows]


def _assert_evidence_table(conn: sqlite3.Connection) -> None:
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='web_verification_evidence'"
    ).fetchone()
    if not exists:
        raise RuntimeError("Tabella web_verification_evidence assente: eseguire prima il collaudo fonti.")


def _document_from_evidence(row: dict[str, Any], *, tenant_id: str) -> StudioDatasetDocument:
    text = _clean(row.get("content_text") or row.get("excerpt"))
    evidence_id = _clean(row.get("id"))
    title = _expected_display_title(row) or "Fonte ufficiale"
    source_name = _clean(row.get("source_name") or row.get("db_source_name") or row.get("source_code") or "Fonte ufficiale")
    attachment_type = _clean(row.get("attachment_type"))
    mime_type = _mime_type_for_evidence(attachment_type, row)
    sha256 = _clean(row.get("sha256")) or hashlib.sha256(text.encode("utf-8")).hexdigest()
    document_id = stable_id("legal-source", evidence_id, row.get("evidence_key"), row.get("source_url"), row.get("attachment_url"), prefix="lsrc-")
    norm_references = _norm_references(text)
    rg_references = _rg_references(text)
    return StudioDatasetDocument(
        tenant_id=tenant_id,
        document_id=document_id,
        title=title,
        text=text,
        source_name=source_name,
        mime_type=mime_type,
        source_kind="legal_web_evidence",
        fascicolo_id=_clean(row.get("source_code")) or "fonti_ufficiali",
        sha256=sha256,
        pages=(DocumentPage(page_number=1, text=text, metadata={"evidence_id": int(row.get("id") or 0)}),),
        metadata={
            "evidence_id": int(row.get("id") or 0),
            "evidence_key": _clean(row.get("evidence_key")),
            "review_id": int(row.get("review_id") or 0),
            "normalized_document_id": int(row.get("normalized_document_id") or 0),
            "source_code": _clean(row.get("source_code")),
            "source_name": source_name,
            "source_url": _clean(row.get("source_url") or row.get("raw_source_url")),
            "attachment_url": _clean(row.get("attachment_url")),
            "attachment_type": attachment_type,
            "origin": _clean(row.get("origin")),
            "verification_status": _clean(row.get("verification_status")),
            "is_official": bool(row.get("is_official")),
            "context_chars": int(row.get("context_chars") or 0),
            "matched_terms": _json_list(row.get("matched_terms_json")),
            "norm_references": norm_references,
            "rg_references": rg_references,
            "corpus_source": "web_verification_evidence",
        },
    )


def _manifest(
    options: SourceCorpusOptions,
    rows: list[dict[str, Any]],
    documents: list[StudioDatasetDocument],
    chunks: list[Any],
    document_ai_path: Path,
) -> dict[str, Any]:
    return {
        "schema": "iusentra.lex_source_corpus.v1",
        "created_at": _now(),
        "tenant_id": options.tenant_id,
        "intelligence_db": str(options.intelligence_db),
        "documents_count": len(documents),
        "chunks_count": len(chunks),
        "evidence_count": len(rows),
        "statuses": list(options.statuses),
        "source_codes": list(options.source_codes),
        "source_filters": {
            code: "solo schede documentali Cassazione: civile, penale, questioni, rinvii e relazioni"
            for code in options.source_codes
            if code in CASSAZIONE_DOCUMENT_SOURCE_CODES
        },
        "review_ids": list(options.review_ids),
        "min_context_chars": options.min_context_chars,
        "document_ai_json": str(document_ai_path),
        "memory_tree": {
            "schema": "iusentra.lex_memory_tree.v1",
            "path": str(options.output_dir / "memory_tree"),
            "policy": "memoria strutturata deterministica per RAG Lex, senza chiamate LLM",
            "tokenjuice_schema": "iusentra.lex_tokenjuice.v1",
            "tokenjuice_policy": "contesto compattato in modo deterministico prima del modello",
        },
        "automatic_training": False,
        "external_training": False,
        "rag_ready": True,
        "human_review_required_for_rag": False,
        "human_review_required_for_fine_tuning": True,
        "fine_tuning_note": (
            "Le evidenze verificate possono entrare nel RAG senza revisione umana. "
            "La revisione umana resta richiesta solo prima di esportare o usare "
            "Q&A candidate per training/fine-tuning."
        ),
    }


def _document_ai_payload(documents: list[StudioDatasetDocument], rows: list[dict[str, Any]]) -> dict[str, Any]:
    now = _now()
    doc_rows: list[dict[str, Any]] = []
    version_rows: list[dict[str, Any]] = []
    text_rows: list[dict[str, Any]] = []
    for document, row in zip(documents, rows, strict=True):
        version_id = f"{document.document_id}-v1"
        safe_filename = f"{document.document_id}.txt"
        doc_rows.append(
            {
                "id": document.document_id,
                "tenant_id": document.tenant_id,
                "fascicolo_id": document.fascicolo_id,
                "original_filename": document.title,
                "safe_filename": safe_filename,
                "file_type": "txt",
                "mime_type": "text/plain",
                "size_bytes": len(document.all_text().encode("utf-8")),
                "sha256": document.sha256,
                "status": "ready",
                "current_version_id": version_id,
                "page_count": 1,
                "created_by": "lex-source-corpus",
                "created_at": now,
                "updated_at": now,
            }
        )
        version_rows.append(
            {
                "id": version_id,
                "tenant_id": document.tenant_id,
                "fascicolo_id": document.fascicolo_id,
                "document_id": document.document_id,
                "version_number": 1,
                "storage_path": f"{document.tenant_id}/fonti/{document.document_id}/v1/{safe_filename}",
                "sha256": document.sha256,
                "source": "web_verification_evidence",
                "created_by": "lex-source-corpus",
                "created_at": now,
            }
        )
        text_rows.append(
            {
                "document_id": document.document_id,
                "version_id": version_id,
                "tenant_id": document.tenant_id,
                "fascicolo_id": document.fascicolo_id,
                "text": document.all_text(),
                "pages": [page.to_dict() for page in document.pages],
                "extraction_engine": _clean(row.get("attachment_type")) or _clean(row.get("origin")) or "web_verification_evidence",
                "created_at": now,
                "warnings": [],
            }
        )
    return {"documents": doc_rows, "versions": version_rows, "texts": text_rows, "audit_events": []}


def _expected_query(row: dict[str, Any]) -> dict[str, Any]:
    title = _expected_display_title(row)
    attachment_url = _clean(row.get("attachment_url"))
    evidence_text = " ".join(
        _clean(part)
        for part in (
            row.get("content_text"),
            row.get("excerpt"),
            row.get("matched_terms_json"),
            row.get("query"),
            row.get("source_url"),
            row.get("raw_source_url"),
            title,
        )
    )
    norm_refs = _norm_references(evidence_text)
    rg_refs = _rg_references(evidence_text)
    return {
        "evidence_id": int(row.get("id") or 0),
        "review_id": int(row.get("review_id") or 0),
        "query": f"Quale allegato ufficiale ha {title}?" if attachment_url else f"Fonte ufficiale {title}",
        "expected_title": title,
        "expected_source_url": _clean(row.get("source_url") or row.get("raw_source_url")),
        "expected_attachment_url": attachment_url,
        "expected_sha256": _clean(row.get("sha256")),
        "expected_terms": _json_list(row.get("matched_terms_json")),
        "expected_norm_references": norm_refs,
        "expected_rg_references": rg_refs,
        "question_matrix": _expected_question_matrix(
            title,
            bool(attachment_url),
            context_text=evidence_text,
            has_norm_refs=bool(norm_refs),
            has_rg_discrepancy=len(set(rg_refs)) > 1,
        ),
    }


def _expected_display_title(row: dict[str, Any]) -> str:
    title = _clean(row.get("title"))
    normalized_title = _clean(row.get("normalized_title"))
    if title.lower().endswith(".pdf") and normalized_title:
        return normalized_title
    return title or normalized_title


def _norm_references(text: str) -> list[str]:
    return legal_reference_labels(
        extract_legal_references(text or ""),
        allowed_types=("article", "act", "eu_act"),
        limit=16,
    )


def _rg_references(text: str) -> list[str]:
    return _unique(RG_REFERENCE_RE.findall(text or ""), limit=16)


def _contextual_question_rows(
    subject: str,
    *,
    context_text: str,
    has_attachment: bool,
    has_norm_refs: bool,
    has_rg_discrepancy: bool,
) -> list[tuple[str, str]]:
    title_lowered = subject.lower()
    context_lowered = context_text.lower()
    is_pending_question = (
        "pendente" in title_lowered
        or "qsp_dettaglio" in context_lowered
        or "qsc_dettaglio" in context_lowered
    )
    is_judgment = "sentenza" in title_lowered and not is_pending_question
    is_order = "ordinanza" in title_lowered
    is_interlocutory = (
        not is_judgment
        and (
            "interlocutoria" in title_lowered
            or "ordinanza interlocutoria" in context_lowered
            or "ordinanza di rimessione" in context_lowered
        )
    )
    is_order = is_order or is_interlocutory
    norm_refs = _norm_references(context_text) if has_norm_refs else []
    rg_refs = _rg_references(context_text)
    rows = [
        (str(item.get("check") or ""), str(item.get("question") or ""))
        for item in build_contextual_question_matrix(
            title=subject,
            context_text=context_text,
            has_attachment=has_attachment,
            norm_references=norm_refs,
            rg_references=rg_refs,
            has_rg_discrepancy=has_rg_discrepancy,
        )
        if item.get("check") and item.get("question")
    ]
    extra_rows: list[tuple[str, str]] = []
    if is_pending_question:
        extra_rows.extend(
            [
                ("stato_pendenza", "La questione è ancora pendente e risultano udienza, relatore o ricorrente?"),
                ("contrasto", "Dal testo emerge un contrasto giurisprudenziale o una ragione di rimessione?"),
            ]
        )
    elif is_interlocutory:
        extra_rows.extend(
            [
                ("natura_rimessione", "L'atto rimette la questione alle Sezioni Unite o ad altro collegio?"),
                ("esito_procedurale", "Quale effetto processuale produce l'ordinanza interlocutoria?"),
            ]
        )
    elif is_judgment:
        extra_rows.extend(
            [
                ("principio", "Qual è il principio di diritto affermato dalla sentenza?"),
                ("decisione", "Qual è l'esito del giudizio e cosa ha deciso la Corte?"),
                ("massima_operativa", "Quale massima operativa può usare l'avvocato senza forzare il testo?"),
            ]
        )
    elif is_order:
        extra_rows.append(("esito_ordinanza", "Qual è l'esito dell'ordinanza?"))
    seen = {key for key, _question in rows}
    for key, question in extra_rows:
        if key and key not in seen:
            rows.append((key, question))
            seen.add(key)
    return rows


def _expected_question_matrix(
    title: str,
    has_attachment: bool,
    *,
    context_text: str,
    has_norm_refs: bool,
    has_rg_discrepancy: bool,
) -> list[dict[str, str]]:
    subject = title or "questa fonte"
    contextual_rows = _contextual_question_rows(
        subject,
        context_text=context_text,
        has_attachment=has_attachment,
        has_norm_refs=has_norm_refs,
        has_rg_discrepancy=has_rg_discrepancy,
    )
    if contextual_rows:
        return [{"check": key, "question": question} for key, question in contextual_rows]
    rows = [
        ("sintesi", f"Mi puoi sintetizzare {subject}?"),
        ("natura_atto", "È una sentenza definitiva, un'ordinanza, una questione pendente o un altro atto?"),
        ("oggetto", "Qual è l'oggetto della questione o della decisione?"),
        ("stato", "Qual è lo stato del procedimento o dell'atto?"),
        ("punto_diritto", "Qual è il punto di diritto o il principio in discussione?"),
        ("motivi", "Quali sono i motivi, le censure o i passaggi rilevanti indicati nel testo?"),
        ("norme", "Quali norme sono richiamate e perché contano?"),
        ("effetto_pratico", "Qual è l'effetto pratico per un avvocato che deve usare questa fonte?"),
        ("esito", "Risulta già un esito finale oppure la questione è ancora pendente?"),
    ]
    if has_attachment:
        rows.append(("pdf_allegato", "Quale PDF o allegato ufficiale è collegato e il link è cliccabile?"))
    rows.append(("discrepanze", "Ci sono discrepanze tra scheda, PDF, metadati o riferimenti numerici?"))
    return [{"check": key, "question": question} for key, question in rows]


def _prepare_output_dir(path: Path, *, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise FileExistsError(f"Cartella non vuota: {path}. Usa --overwrite per rigenerare.")
    path.mkdir(parents=True, exist_ok=True)
    if overwrite:
        for child in path.iterdir():
            if child.is_dir():
                import shutil

                shutil.rmtree(child)
            else:
                child.unlink()


def _mime_type_for_evidence(attachment_type: str, row: dict[str, Any]) -> str:
    if attachment_type == "pdf":
        return "application/pdf"
    if attachment_type == "xml":
        return "application/xml"
    if attachment_type == "docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if attachment_type == "doc":
        return "application/msword"
    if _clean(row.get("attachment_url")):
        return "application/octet-stream"
    return "text/html"


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _unique(values: Iterable[Any], *, limit: int = 16) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        cleaned = _clean(value)
        key = cleaned.lower()
        if not cleaned or key in seen:
            continue
        seen.add(key)
        rows.append(cleaned)
        if len(rows) >= limit:
            break
    return rows


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
