"""Memory Tree deterministico per il corpus Lex.

Il modulo non chiama LLM e non naviga il web. Trasforma documenti già letti
in memoria strutturata: provenienza, qualità, riferimenti normativi/R.G.,
chunk deterministici e ricerca leggera per fonte, norma, R.G. e argomento.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from lex.dataset.chunking import ChunkingOptions, chunk_plain_text
from lex.dataset.models import StudioDatasetDocument, clean_text
from lex.tokenjuice import compress_lex_context, tokenjuice_metadata


MEMORY_TREE_SCHEMA = "iusentra.lex_memory_tree.v1"
DEFAULT_MEMORY_TREE_DIR = "memory_tree"


_NORM_RE = re.compile(
    r"\bart\.?\s*\d+(?:[- bisterquater]*\d*)?"
    r"(?:\s*,?\s*(?:co\.?|comma)\s*\d+)?"
    r"(?:\s+(?:c\.p\.p\.|c\.p\.|c\.p\.c\.|c\.c\.|cost\.|cod\. proc\. pen\.|cod\. pen\.|cod\. civ\.))?",
    re.I,
)
_RG_RE = re.compile(
    r"\b(?:R\.?\s*G\.?|ricorso)\s*(?:n\.?|num\.?)?\s*\d{1,8}\s*/\s*(?:19|20)\d{2}\b",
    re.I,
)
_DATE_RE = re.compile(
    r"\b\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}\b|"
    r"\b\d{1,2}\s+"
    r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
    r"\s+(?:19|20)\d{2}\b",
    re.I,
)
_OCR_NOISE_RE = re.compile(r"(?:\b[a-zA-Z]\s*\|\s*[a-zA-Z]\b|[^\w\s]{6,}|(?:\s+[|_]\s+){2,})")
_WORD_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9'._/-]{2,}")
_STOPWORDS = {
    "alla",
    "allo",
    "agli",
    "alle",
    "della",
    "dello",
    "degli",
    "delle",
    "del",
    "con",
    "per",
    "non",
    "una",
    "uno",
    "che",
    "nel",
    "nella",
    "nelle",
    "sono",
    "questo",
    "questa",
    "sentenza",
    "ordinanza",
    "questione",
    "ricorso",
    "penale",
    "civile",
}


@dataclass(frozen=True, slots=True)
class LexMemoryProvenance:
    tenant_id: str
    document_id: str
    title: str
    source_kind: str
    source_name: str = ""
    source_code: str = ""
    fascicolo_id: str = ""
    source_url: str = ""
    attachment_url: str = ""
    attachment_type: str = ""
    sha256: str = ""
    official: bool = False
    review_id: int = 0
    evidence_id: int = 0

    def to_dict(self) -> dict[str, Any]:
        return _compact(asdict(self))


@dataclass(frozen=True, slots=True)
class LexMemoryQuality:
    status: str
    ready: bool
    text_chars: int
    has_text: bool
    has_pdf: bool
    has_hash: bool
    ocr_dirty: bool
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["notes"] = list(self.notes)
        return _compact(payload)


@dataclass(frozen=True, slots=True)
class LexMemoryChunk:
    chunk_id: str
    document_id: str
    tenant_id: str
    chunk_index: int
    text: str
    content_hash: str
    provenance: LexMemoryProvenance
    quality: LexMemoryQuality
    norms: tuple[str, ...] = ()
    rg_refs: tuple[str, ...] = ()
    dates: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, include_text: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        payload["provenance"] = self.provenance.to_dict()
        payload["quality"] = self.quality.to_dict()
        payload["norms"] = list(self.norms)
        payload["rg_refs"] = list(self.rg_refs)
        payload["dates"] = list(self.dates)
        payload["topics"] = list(self.topics)
        if not include_text:
            payload.pop("text", None)
        return _compact(payload)


@dataclass(frozen=True, slots=True)
class LexMemoryTree:
    schema: str
    created_at: str
    documents_count: int
    chunks_count: int
    ready_documents_count: int
    not_ready_documents_count: int
    sources: tuple[str, ...]
    norms: tuple[str, ...]
    rg_refs: tuple[str, ...]
    topics: tuple[str, ...]
    documents: tuple[dict[str, Any], ...]
    chunks: tuple[LexMemoryChunk, ...]

    def summary(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "created_at": self.created_at,
            "documents_count": self.documents_count,
            "chunks_count": self.chunks_count,
            "ready_documents_count": self.ready_documents_count,
            "not_ready_documents_count": self.not_ready_documents_count,
            "sources": list(self.sources),
            "norms": list(self.norms),
            "rg_refs": list(self.rg_refs),
            "topics": list(self.topics),
        }


def build_lex_memory_tree(
    documents: Iterable[StudioDatasetDocument],
    *,
    max_chars: int = 1800,
    overlap_chars: int = 180,
) -> LexMemoryTree:
    rows = list(documents)
    chunks: list[LexMemoryChunk] = []
    document_rows: list[dict[str, Any]] = []
    ready_documents = 0

    for document in rows:
        provenance = _provenance_from_document(document)
        text = _normalise_memory_text(document.all_text())
        quality = _quality_for_document(document, text=text, provenance=provenance)
        if quality.ready:
            ready_documents += 1
        document_rows.append(
            {
                "document_id": document.document_id,
                "tenant_id": document.tenant_id,
                "title": document.title,
                "provenance": provenance.to_dict(),
                "quality": quality.to_dict(),
                "norms": _extract_norms(text),
                "rg_refs": _extract_rg_refs(text, document.title, provenance.source_url, provenance.attachment_url),
                "topics": _extract_topics(text, document.title),
            }
        )
        chunks.extend(
            _chunks_for_document(
                document,
                text=text,
                provenance=provenance,
                quality=quality,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
        )

    return LexMemoryTree(
        schema=MEMORY_TREE_SCHEMA,
        created_at=_now(),
        documents_count=len(rows),
        chunks_count=len(chunks),
        ready_documents_count=ready_documents,
        not_ready_documents_count=len(rows) - ready_documents,
        sources=tuple(sorted({chunk.provenance.source_code or chunk.provenance.source_name for chunk in chunks if chunk.provenance.source_code or chunk.provenance.source_name})),
        norms=tuple(sorted({norm for chunk in chunks for norm in chunk.norms})),
        rg_refs=tuple(sorted({rg for chunk in chunks for rg in chunk.rg_refs})),
        topics=tuple(sorted({topic for chunk in chunks for topic in chunk.topics})[:200]),
        documents=tuple(document_rows),
        chunks=tuple(chunks),
    )


def write_lex_memory_tree(tree: LexMemoryTree, output_dir: Path | str) -> dict[str, Any]:
    root = Path(output_dir) / DEFAULT_MEMORY_TREE_DIR
    root.mkdir(parents=True, exist_ok=True)
    summary_path = root / "index.json"
    documents_path = root / "documents.jsonl"
    chunks_path = root / "chunks.jsonl"

    summary_path.write_text(json.dumps(tree.summary(), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_jsonl(documents_path, tree.documents)
    _write_jsonl(chunks_path, (chunk.to_dict(include_text=True) for chunk in tree.chunks))

    return {
        "memory_tree_dir": str(root),
        "memory_tree_index": str(summary_path),
        "memory_tree_documents": str(documents_path),
        "memory_tree_chunks": str(chunks_path),
        **tree.summary(),
    }


def build_and_write_lex_memory_tree(
    documents: Iterable[StudioDatasetDocument],
    output_dir: Path | str,
    *,
    max_chars: int = 1800,
    overlap_chars: int = 180,
) -> dict[str, Any]:
    tree = build_lex_memory_tree(documents, max_chars=max_chars, overlap_chars=overlap_chars)
    return write_lex_memory_tree(tree, output_dir)


def search_lex_memory_chunks(
    chunks: Iterable[LexMemoryChunk | dict[str, Any]],
    query: str,
    *,
    limit: int = 10,
) -> list[dict[str, Any]]:
    query_text = _normalise_memory_text(query).lower()
    if not query_text:
        return []
    query_terms = set(_terms(query_text))
    query_norms = set(_extract_norms(query_text))
    query_rgs = set(_extract_rg_refs(query_text))
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in chunks:
        row = item.to_dict() if isinstance(item, LexMemoryChunk) else dict(item)
        score = _score_memory_row(row, query_text, query_terms, query_norms, query_rgs)
        if score > 0:
            row["score"] = score
            scored.append((score, row))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("chunk_id", "")))
    return [row for _, row in scored[: max(1, int(limit or 1))]]


def load_lex_memory_chunks(chunks_path: Path | str) -> list[dict[str, Any]]:
    path = Path(chunks_path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _chunks_for_document(
    document: StudioDatasetDocument,
    *,
    text: str,
    provenance: LexMemoryProvenance,
    quality: LexMemoryQuality,
    max_chars: int,
    overlap_chars: int,
) -> list[LexMemoryChunk]:
    if not text:
        return []
    chunks = chunk_plain_text(
        text,
        ChunkingOptions(max_chars=max(240, max_chars), overlap_chars=max(0, overlap_chars), min_chars=40),
    )
    rows: list[LexMemoryChunk] = []
    for index, chunk_text in enumerate(chunks, start=1):
        chunk_hash = _sha256(chunk_text)
        chunk_id = _stable_chunk_id(document.tenant_id, document.document_id, index, chunk_hash)
        compact_context = compress_lex_context(
            chunk_text,
            source_type=document.mime_type or document.source_kind,
            max_chars=min(1200, max(360, max_chars)),
        )
        rows.append(
            LexMemoryChunk(
                chunk_id=chunk_id,
                document_id=document.document_id,
                tenant_id=document.tenant_id,
                chunk_index=index,
                text=chunk_text,
                content_hash=chunk_hash,
                provenance=provenance,
                quality=quality,
                norms=tuple(_extract_norms(chunk_text)),
                rg_refs=tuple(_extract_rg_refs(chunk_text, document.title, provenance.source_url, provenance.attachment_url)),
                dates=tuple(_extract_dates(chunk_text)),
                topics=tuple(_extract_topics(chunk_text, document.title)),
                metadata={
                    "memory_tree_schema": MEMORY_TREE_SCHEMA,
                    "rag_ready": quality.ready,
                    "source_kind": document.source_kind,
                    "tokenjuice": tokenjuice_metadata(compact_context),
                },
            )
        )
    return rows


def _quality_for_document(
    document: StudioDatasetDocument,
    *,
    text: str,
    provenance: LexMemoryProvenance,
) -> LexMemoryQuality:
    metadata = dict(document.metadata or {})
    text_chars = len(text)
    has_text = text_chars > 0
    has_pdf = _looks_like_pdf(provenance.attachment_url, provenance.attachment_type, document.mime_type)
    has_hash = bool(provenance.sha256 or document.sha256)
    ocr_dirty = _looks_ocr_dirty(text)
    notes: list[str] = []
    status = "pronto"

    if not has_text:
        status = "testo_mancante"
        notes.append("testo assente")
    elif ocr_dirty:
        status = "da_ocr"
        notes.append("testo OCR da ripulire prima della risposta finale")
    elif str(metadata.get("verification_status") or "").lower() not in {"", "verified", "verificata", "ok"}:
        status = "pronto_con_note"
        notes.append("stato fonte da verificare")

    if has_pdf and not has_hash:
        status = "pronto_con_note" if has_text else status
        notes.append("PDF senza hash registrato")

    rg_refs = _extract_rg_refs(text, document.title, provenance.source_url, provenance.attachment_url)
    if len(set(rg_refs)) > 1:
        status = "pronto_con_note" if status == "pronto" else status
        notes.append("riferimenti R.G. multipli da distinguere in risposta")

    return LexMemoryQuality(
        status=status,
        ready=status in {"pronto", "pronto_con_note", "da_ocr"} and has_text,
        text_chars=text_chars,
        has_text=has_text,
        has_pdf=has_pdf,
        has_hash=has_hash,
        ocr_dirty=ocr_dirty,
        notes=tuple(dict.fromkeys(notes)),
    )


def _provenance_from_document(document: StudioDatasetDocument) -> LexMemoryProvenance:
    metadata = dict(document.metadata or {})
    return LexMemoryProvenance(
        tenant_id=document.tenant_id,
        document_id=document.document_id,
        title=document.title,
        source_kind=document.source_kind,
        source_name=_first_text(document.source_name, metadata.get("source_name")),
        source_code=clean_text(metadata.get("source_code")),
        fascicolo_id=document.fascicolo_id,
        source_url=clean_text(metadata.get("source_url")),
        attachment_url=clean_text(metadata.get("attachment_url")),
        attachment_type=clean_text(metadata.get("attachment_type")),
        sha256=clean_text(document.sha256 or metadata.get("sha256")),
        official=bool(metadata.get("is_official") or metadata.get("official")),
        review_id=_safe_int(metadata.get("review_id")),
        evidence_id=_safe_int(metadata.get("evidence_id")),
    )


def _score_memory_row(
    row: dict[str, Any],
    query_text: str,
    query_terms: set[str],
    query_norms: set[str],
    query_rgs: set[str],
) -> int:
    text = _normalise_memory_text(row.get("text")).lower()
    provenance = row.get("provenance") or {}
    haystack = " ".join(
        [
            text,
            str(provenance.get("title") or ""),
            str(provenance.get("source_name") or ""),
            str(provenance.get("source_code") or ""),
            " ".join(row.get("norms") or []),
            " ".join(row.get("rg_refs") or []),
            " ".join(row.get("topics") or []),
        ]
    ).lower()
    score = 0
    if query_text and query_text in haystack:
        score += 15
    row_norms = set(str(item).lower() for item in row.get("norms") or [])
    row_rgs = set(_normalise_rg(str(item)) for item in row.get("rg_refs") or [])
    score += 25 * len(set(n.lower() for n in query_norms) & row_norms)
    score += 40 * len(set(_normalise_rg(r) for r in query_rgs) & row_rgs)
    score += 4 * len(query_terms & set(_terms(haystack)))
    if (row.get("quality") or {}).get("ready"):
        score += 3
    if (provenance or {}).get("official"):
        score += 2
    return score


def _extract_norms(*values: Any) -> list[str]:
    found: list[str] = []
    for value in values:
        text = str(value or "")
        for match in _NORM_RE.finditer(text):
            norm = _normalise_norm(match.group(0))
            if norm and norm not in found:
                found.append(norm)
    return found[:50]


def _extract_rg_refs(*values: Any) -> list[str]:
    found: list[str] = []
    for value in values:
        text = str(value or "")
        for match in _RG_RE.finditer(text):
            ref = _normalise_rg(match.group(0))
            if ref and ref not in found:
                found.append(ref)
    return found[:30]


def _extract_dates(text: str) -> list[str]:
    found = []
    for match in _DATE_RE.finditer(str(text or "")):
        value = clean_text(match.group(0))
        if value and value not in found:
            found.append(value)
    return found[:30]


def _extract_topics(text: str, title: str = "") -> list[str]:
    terms = _terms(f"{title} {text}")
    counts: dict[str, int] = {}
    for term in terms:
        if term in _STOPWORDS or len(term) < 4 or term.isdigit():
            continue
        counts[term] = counts.get(term, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [term for term, _ in ordered[:20]]


def _terms(text: str) -> list[str]:
    return [match.group(0).lower().strip(".,;:()[]") for match in _WORD_RE.finditer(str(text or ""))]


def _looks_ocr_dirty(text: str) -> bool:
    value = str(text or "")
    if not value:
        return False
    sample = value[:5000]
    if sample.count("|") >= 3:
        return True
    if _OCR_NOISE_RE.search(sample):
        return True
    words = _terms(sample)
    if len(sample) > 400 and words:
        short_words = sum(1 for word in words if len(word) <= 2)
        return short_words / max(1, len(words)) > 0.25
    return False


def _looks_like_pdf(*values: Any) -> bool:
    text = " ".join(str(value or "").lower() for value in values)
    return ".pdf" in text or text.strip() == "pdf" or "application/pdf" in text


def _normalise_memory_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    return "\n\n".join(" ".join(part.split()) for part in text.split("\n\n") if part.strip()).strip()


def _normalise_norm(value: str) -> str:
    text = clean_text(value).replace("Art ", "art. ")
    text = re.sub(r"\barticolo\b", "art.", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;,")


def _normalise_rg(value: str) -> str:
    text = clean_text(value)
    match = re.search(r"(\d{1,8})\s*/\s*((?:19|20)\d{2})", text)
    if not match:
        return text
    return f"R.G. {match.group(1)}/{match.group(2)}"


def _stable_chunk_id(*parts: Any) -> str:
    return "lex-mem-" + _sha256("\n".join(str(part or "") for part in parts))[:24]


def _sha256(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(tz=UTC).isoformat()


def _first_text(*values: Any) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _compact(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value not in (None, "", [], {}, ())}


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
