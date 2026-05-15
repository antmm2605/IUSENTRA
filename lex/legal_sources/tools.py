"""Internal Python tools for Lex AI Legal Source Engine.

These are not public routes. They are narrow interfaces that can be wired into
Lex AI later after RBAC, audit and UI review.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_policy import AnswerPolicy
from .citations import deduplicate_citations
from .models import LegalAnswerDraft, RetrievedLegalPassage
from .retriever import LegalSourceRetriever


@dataclass(slots=True)
class LegalSourceToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    refusal: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LegalSourceTools:
    def __init__(
        self,
        *,
        retriever: LegalSourceRetriever | None = None,
        answer_policy: AnswerPolicy | None = None,
    ) -> None:
        self.retriever = retriever or LegalSourceRetriever()
        self.answer_policy = answer_policy or AnswerPolicy()

    def search_legal_sources(self, query: str, **filters: Any) -> LegalSourceToolResult:
        passages = self.retriever.combined_search(query, **filters)
        if not passages:
            return _refusal("insufficient_sources", "Nessuna fonte citabile recuperata dall'indice locale.")
        return LegalSourceToolResult(ok=True, data={"passages": [passage.to_dict() for passage in passages]})

    def get_legal_document(self, identifier: str, **filters: Any) -> LegalSourceToolResult:
        passages = self.retriever.exact_lookup(identifier, **filters)
        if not passages:
            return _refusal("document_not_found", "Documento non disponibile nell'indice locale configurato.")
        return LegalSourceToolResult(ok=True, data={"passages": [passage.to_dict() for passage in passages]})

    def get_article(self, act_identifier: str, article: str, **filters: Any) -> LegalSourceToolResult:
        passages = self.retriever.article_lookup(act_identifier, article, **filters)
        if not passages:
            return _refusal("article_not_found", "Articolo non disponibile nell'indice locale configurato.")
        return LegalSourceToolResult(ok=True, data={"passages": [passage.to_dict() for passage in passages]})

    def get_case_law(self, identifier: str, **filters: Any) -> LegalSourceToolResult:
        passages = self.retriever.exact_lookup(identifier, document_family="case_law", **filters)
        if not passages:
            return _refusal("case_law_not_found", "Pronuncia non disponibile nell'indice locale configurato.")
        return LegalSourceToolResult(ok=True, data={"passages": [passage.to_dict() for passage in passages]})

    def compare_versions(self, identifier: str, version_a: str, version_b: str, **filters: Any) -> LegalSourceToolResult:
        _ = identifier, version_a, version_b, filters
        return _refusal("version_compare_unavailable", "Confronto versioni non disponibile senza indice versionato.")

    def explain_with_sources(self, question: str, passages: list[RetrievedLegalPassage] | None = None) -> LegalSourceToolResult:
        selected = list(passages or self.retriever.combined_search(question))
        if not selected:
            return _refusal("insufficient_sources", "Non posso rispondere senza passaggi fonte citabili.")
        citations = deduplicate_citations(passage.citation for passage in selected if passage.citation)
        answer = "Dalle fonti recuperate risultano questi passaggi: " + " ".join(
            passage.text.strip() for passage in selected if passage.text.strip()
        )
        draft = LegalAnswerDraft(
            question=question,
            answer=answer,
            passages=selected,
            citations=citations,
            confidence=min(0.85, max(0.1, sum(p.score for p in selected) / max(1, len(selected)))),
        )
        policy = self.answer_policy.validate(draft)
        if not policy.allowed:
            return LegalSourceToolResult(
                ok=False,
                refusal={"reason": "answer_policy_failed", "policy": policy.to_dict()},
                warnings=[warning.message for warning in policy.warnings],
            )
        return LegalSourceToolResult(
            ok=True,
            data={
                "answer_draft": draft.answer,
                "citations": [citation.to_dict() for citation in citations],
                "policy": policy.to_dict(),
            },
            warnings=[warning.message for warning in policy.warnings],
        )


def _refusal(reason: str, message: str) -> LegalSourceToolResult:
    return LegalSourceToolResult(ok=False, refusal={"reason": reason, "message": message})


_DEFAULT_TOOLS = LegalSourceTools()


def search_legal_sources(query: str, **filters: Any) -> dict[str, Any]:
    return _DEFAULT_TOOLS.search_legal_sources(query, **filters).to_dict()


def get_legal_document(identifier: str, **filters: Any) -> dict[str, Any]:
    return _DEFAULT_TOOLS.get_legal_document(identifier, **filters).to_dict()


def get_article(act_identifier: str, article: str, **filters: Any) -> dict[str, Any]:
    return _DEFAULT_TOOLS.get_article(act_identifier, article, **filters).to_dict()


def get_case_law(identifier: str, **filters: Any) -> dict[str, Any]:
    return _DEFAULT_TOOLS.get_case_law(identifier, **filters).to_dict()


def compare_versions(identifier: str, version_a: str, version_b: str, **filters: Any) -> dict[str, Any]:
    return _DEFAULT_TOOLS.compare_versions(identifier, version_a, version_b, **filters).to_dict()


def explain_with_sources(question: str, passages: list[RetrievedLegalPassage] | None = None) -> dict[str, Any]:
    return _DEFAULT_TOOLS.explain_with_sources(question, passages).to_dict()


__all__ = [
    "LegalSourceToolResult",
    "LegalSourceTools",
    "compare_versions",
    "explain_with_sources",
    "get_article",
    "get_case_law",
    "get_legal_document",
    "search_legal_sources",
]
