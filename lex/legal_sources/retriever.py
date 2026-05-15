"""Local retriever for the Legal Source Engine."""

from __future__ import annotations

import json
import re
from functools import cached_property
from pathlib import Path
from typing import Any

from .models import LegalCitation, RetrievedLegalPassage
from .settings import LegalSourceEngineSettings


class LegalSourceRetriever:
    """Safe local retriever.

    This class never performs network calls and does not require embeddings. It
    reads the JSONL index produced by ``lex.legal_sources.populate``. If no
    local index exists, methods return empty lists rather than guessing.
    """

    def __init__(
        self,
        *,
        settings: LegalSourceEngineSettings | None = None,
        full_text_index: Any | None = None,
        semantic_index: Any | None = None,
        index_path: str | Path | None = None,
        auto_populate: bool | None = None,
    ) -> None:
        self.settings = settings or LegalSourceEngineSettings.from_env()
        self.full_text_index = full_text_index
        self.semantic_index = semantic_index
        self.index_path = Path(index_path) if index_path else self.settings.index_dir / "passages.jsonl"
        should_auto_populate = self.settings.auto_populate if auto_populate is None else bool(auto_populate)
        if should_auto_populate and self.settings.enabled and not self.index_path.exists():
            from .populate import ensure_operational_index

            ensure_operational_index(settings=self.settings)

    def exact_lookup(self, identifier: str, **filters: Any) -> list[RetrievedLegalPassage]:
        needle = _normalize(identifier)
        if not needle:
            return []
        rows = []
        for passage in self._filtered_passages(filters):
            citation = passage.citation
            identifiers = [
                passage.metadata.get("stable_identifier"),
                passage.metadata.get("document_id"),
                citation.urn,
                citation.eli,
                citation.celex,
                citation.ecli,
                citation.hudoc_id,
                citation.url,
                citation.number,
                citation.title,
                citation.source_id,
            ]
            if any(needle == _normalize(value) or needle in _normalize(value) for value in identifiers):
                rows.append(_with_method(passage, "local_exact_lookup", score_boost=0.25))
        return _rank_passages(rows, limit=filters.get("limit"))

    def article_lookup(self, act_identifier: str, article: str, **filters: Any) -> list[RetrievedLegalPassage]:
        candidates = self.exact_lookup(act_identifier, **filters)
        article_needle = _normalize(article)
        if not article_needle:
            return candidates
        rows = [
            _with_method(passage, "local_article_lookup", score_boost=0.2)
            for passage in candidates
            if article_needle in _normalize(passage.citation.article)
            or article_needle in _normalize(passage.metadata.get("article"))
            or article_needle in _normalize(passage.text)
        ]
        return _rank_passages(rows, limit=filters.get("limit"))

    def full_text_search(self, query: str, **filters: Any) -> list[RetrievedLegalPassage]:
        tokens = _tokens(query)
        if not tokens:
            return []
        rows: list[RetrievedLegalPassage] = []
        for passage in self._filtered_passages(filters):
            haystack = _normalize(
                " ".join(
                    [
                        passage.text,
                        passage.citation.title,
                        passage.citation.source_name,
                        passage.citation.source_category,
                        json.dumps(passage.metadata, ensure_ascii=False),
                    ]
                )
            )
            hits = sum(1 for token in tokens if token in haystack)
            if hits <= 0:
                continue
            score = min(1.0, passage.score + (hits / max(8, len(tokens) * 4)))
            rows.append(_with_method(passage, "local_full_text", score=score))
        return _rank_passages(rows, limit=filters.get("limit"))

    def semantic_search(self, query: str, **filters: Any) -> list[RetrievedLegalPassage]:
        _ = query, filters
        # TODO: wire to an explicit semantic index after embedding storage policy.
        return []

    def combined_search(self, query: str, **filters: Any) -> list[RetrievedLegalPassage]:
        rows: list[RetrievedLegalPassage] = []
        rows.extend(self.exact_lookup(query, **filters))
        rows.extend(self.full_text_search(query, **filters))
        rows.extend(self.semantic_search(query, **filters))
        return _rank_passages(_deduplicate_passages(rows), limit=filters.get("limit"))

    @cached_property
    def passages(self) -> list[RetrievedLegalPassage]:
        return _load_passages(self.index_path)

    def _filtered_passages(self, filters: dict[str, Any]) -> list[RetrievedLegalPassage]:
        rows = list(self.passages)
        source_id = _normalize(filters.get("source_id") or filters.get("source"))
        category = _normalize(filters.get("category"))
        document_type = _normalize(filters.get("document_type"))
        if source_id:
            rows = [passage for passage in rows if source_id in _normalize(passage.citation.source_id)]
        if category:
            rows = [passage for passage in rows if category in _normalize(passage.citation.source_category)]
        if document_type:
            rows = [passage for passage in rows if document_type in _normalize(passage.citation.document_type)]
        return rows


def _load_passages(path: Path) -> list[RetrievedLegalPassage]:
    if not path.exists():
        return []
    rows: list[RetrievedLegalPassage] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            passage = _passage_from_dict(payload)
            if passage is not None:
                rows.append(passage)
    return rows


def _passage_from_dict(payload: dict[str, Any]) -> RetrievedLegalPassage | None:
    if not isinstance(payload, dict):
        return None
    citation_payload = payload.get("citation")
    if not isinstance(citation_payload, dict):
        return None
    citation = LegalCitation(**{field: citation_payload.get(field, "") for field in LegalCitation.__dataclass_fields__})
    return RetrievedLegalPassage(
        text=str(payload.get("text") or ""),
        citation=citation,
        score=float(payload.get("score") or 0.0),
        retrieval_method=str(payload.get("retrieval_method") or ""),
        source_priority=int(payload.get("source_priority") or 100),
        metadata=dict(payload.get("metadata") or {}),
    )


def _with_method(
    passage: RetrievedLegalPassage,
    retrieval_method: str,
    *,
    score: float | None = None,
    score_boost: float = 0.0,
) -> RetrievedLegalPassage:
    return RetrievedLegalPassage(
        text=passage.text,
        citation=passage.citation,
        score=min(1.0, float(score if score is not None else passage.score + score_boost)),
        retrieval_method=retrieval_method,
        source_priority=passage.source_priority,
        metadata=dict(passage.metadata),
    )


def _rank_passages(passages: list[RetrievedLegalPassage], *, limit: Any = None) -> list[RetrievedLegalPassage]:
    max_rows = 10
    try:
        if limit is not None:
            max_rows = max(1, int(limit))
    except (TypeError, ValueError):
        max_rows = 10
    rows = sorted(passages, key=lambda passage: (-passage.score, passage.source_priority, passage.citation.source_name))
    return rows[:max_rows]


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").split()).strip().lower()


def _tokens(value: Any) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9_]+", _normalize(value)) if len(token) >= 3]


def _deduplicate_passages(passages: list[RetrievedLegalPassage]) -> list[RetrievedLegalPassage]:
    seen: set[tuple[str, str, str]] = set()
    rows: list[RetrievedLegalPassage] = []
    for passage in passages:
        citation = passage.citation
        key = (
            citation.source_id,
            citation.urn or citation.eli or citation.celex or citation.ecli or citation.hudoc_id or citation.url,
            passage.text[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        rows.append(passage)
    return rows


__all__ = ["LegalSourceRetriever"]
