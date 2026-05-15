"""Answer policy for source-grounded legal drafts."""

from __future__ import annotations

import re

from .citations import citation_fingerprint, validate_citation
from .models import LegalAnswerDraft, LegalCitation, PolicyResult, RetrievedLegalPassage


LEGISLATION_CATEGORIES = {"primary_legislation", "regional_legislation", "eu_law"}
PRACTICE_CATEGORIES = {
    "tax_practice",
    "privacy_authority",
    "public_procurement_anticorruption",
    "competition_consumer_authority",
}
PARLIAMENTARY_CATEGORIES = {"parliamentary_materials"}


def _contains_current_law_request(text: str) -> bool:
    haystack = " ".join(str(text or "").lower().split())
    return bool(
        re.search(
            r"\b(vigente|vigenti|attuale|attuali|oggi|ad oggi|in vigore|versione applicabile|diritto vigente)\b",
            haystack,
        )
    )


def _contains_legal_action_request(text: str) -> bool:
    haystack = " ".join(str(text or "").lower().split())
    return bool(
        re.search(
            r"\b(invia|deposit[a-z]*|notific[a-z]*|firma|paga|trasmetti|esegui|presenta il ricorso|manda la pec)\b",
            haystack,
        )
    )


def _has_uncertainty_language(text: str) -> bool:
    haystack = str(text or "").lower()
    return any(marker in haystack for marker in ("non risulta", "sembra", "potrebbe", "da verificare", "fonti insufficienti"))


def _passage_citation_keys(passages: list[RetrievedLegalPassage]) -> set[tuple[str, str, str, str]]:
    return {citation_fingerprint(passage.citation) for passage in passages if passage.citation}


def _citation_matches_passages(citation: LegalCitation, passages: list[RetrievedLegalPassage]) -> bool:
    keys = _passage_citation_keys(passages)
    return citation_fingerprint(citation) in keys


class AnswerPolicy:
    def validate(self, draft: LegalAnswerDraft) -> PolicyResult:
        result = PolicyResult()
        question = draft.question or ""

        if _contains_legal_action_request(question):
            result.add_error(
                "lawyer_review_required",
                "La richiesta implica un'azione dispositiva o ad alto rischio: serve revisione dell'avvocato.",
            )

        if not draft.passages:
            result.add_error("missing_retrieved_passages", "La risposta giuridica richiede passaggi fonte recuperati.")
            return result

        if not draft.has_citations():
            result.add_error("missing_citations", "La risposta giuridica non puo essere prodotta senza citazioni sufficienti.")

        for passage in draft.passages:
            if not passage.text.strip():
                result.add_error("empty_passage", "Un passaggio recuperato e' vuoto.", source_id=passage.citation.source_id)
            citation_result = validate_citation(passage.citation)
            result.merge(citation_result)

        if draft.citations:
            for citation in draft.citations:
                citation_result = validate_citation(citation)
                result.merge(citation_result)
                if citation_result.allowed and not _citation_matches_passages(citation, draft.passages):
                    result.add_error(
                        "citation_not_backed_by_passage",
                        "Una citazione della bozza non corrisponde ad alcun passaggio recuperato.",
                        source_id=citation.source_id,
                    )

        current_law = _contains_current_law_request(question)
        for passage in draft.passages:
            citation = passage.citation
            category = citation.source_category
            if current_law and category in LEGISLATION_CATEGORIES and not citation.version_date:
                result.add_error(
                    "version_date_required",
                    "Per diritto vigente o attuale serve una data di versione della fonte normativa.",
                    source_id=citation.source_id,
                )
            if category in PRACTICE_CATEGORIES:
                result.add_warning(
                    "non_binding_authority_practice",
                    "La fonte e' prassi o guida di autorita: va distinta dal diritto vincolante.",
                    source_id=citation.source_id,
                )
            if category in PARLIAMENTARY_CATEGORIES:
                result.add_warning(
                    "parliamentary_material_not_binding",
                    "Il materiale parlamentare e' preparatorio o informativo, non diritto vigente.",
                    source_id=citation.source_id,
                )

        if draft.confidence < 0.5 and not _has_uncertainty_language(draft.answer):
            result.add_warning(
                "low_confidence_requires_uncertainty",
                "La confidence e' bassa: la bozza deve usare linguaggio di incertezza.",
            )

        return result


__all__ = ["AnswerPolicy", "LEGISLATION_CATEGORIES", "PARLIAMENTARY_CATEGORIES", "PRACTICE_CATEGORIES"]
