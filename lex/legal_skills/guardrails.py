"""Guardrail professionali per output Legal Skills."""

from __future__ import annotations

import re
from typing import Any

from .models import LegalSkillCitation, LegalSkillReviewerNote


UNTRUSTED_INSTRUCTION_RE = re.compile(
    r"(ignore previous instructions|system override|developer message|you are now|leggi ~/.ssh|read ~/.ssh)",
    re.IGNORECASE,
)


def sanitize_untrusted_document_text(text: str) -> tuple[str, list[str]]:
    raw = str(text or "")
    warnings: list[str] = []
    if UNTRUSTED_INSTRUCTION_RE.search(raw):
        warnings.append("Il documento contiene istruzioni non pertinenti: sono state ignorate.")
        raw = UNTRUSTED_INSTRUCTION_RE.sub("[istruzione ignorata]", raw)
    raw = raw.replace("\x00", " ")
    return raw[:20_000], warnings


def enforce_attorney_review_gate(answer: str, *, risk_level: str = "medium") -> LegalSkillReviewerNote:
    reasons = ["Risultato generato come bozza operativa per revisione professionale."]
    if risk_level == "high":
        reasons.append("Richiesta ad alto impatto: verificare fonti, fatti e strategia prima dell'uso.")
    return LegalSkillReviewerNote(
        text="Bozza per revisione: controlla fatti, fonti, termini e strategia prima di usarla nel fascicolo.",
        needs_review=True,
        blocks_export=False,
        reasons=reasons,
    )


def enforce_citation_policy(citations: list[LegalSkillCitation], *, source_mode: str) -> list[str]:
    warnings: list[str] = []
    if source_mode == "strict" and not any(c.source_type in {"official", "internal"} for c in citations):
        warnings.append("Modalita fonti rigorosa: servono fonti ufficiali o documenti interni verificati.")
    if not citations:
        warnings.append("Nessuna fonte verificabile associata al risultato.")
    return warnings


def enforce_jurisdiction_policy(jurisdictions: list[str]) -> list[str]:
    if not jurisdictions or "IT" not in {item.upper() for item in jurisdictions}:
        return ["Profilo giurisdizionale da verificare prima dell'uso in Italia."]
    return []


def enforce_privilege_destination_policy(context: dict[str, Any]) -> list[str]:
    destination = str(context.get("destination") or "").lower()
    if destination and destination not in {"internal", "studio", "fascicolo"}:
        return ["Destinazione esterna rilevata: verificare riservatezza e segreto professionale."]
    return []


def enforce_non_lawyer_gate(profile_roles: list[str]) -> list[str]:
    lowered = {role.lower() for role in profile_roles}
    if lowered and not {"avvocato", "amministratore", "superadmin"} & lowered:
        return ["Utente non qualificato come avvocato: serve approvazione prima dell'uso."]
    return []


def enforce_source_sufficiency(citations: list[LegalSkillCitation], *, source_mode: str) -> tuple[bool, list[str]]:
    warnings = enforce_citation_policy(citations, source_mode=source_mode)
    enough = not warnings or source_mode != "strict"
    return enough, warnings


def classify_output_risk(answer: str, *, request_risk: str = "medium") -> str:
    text = str(answer or "").lower()
    if request_risk == "high" or any(token in text for token in ("termine perentorio", "decadenza", "sanzione", "licenziamento")):
        return "high"
    if any(token in text for token in ("rischio", "verificare", "approvazione")):
        return "medium"
    return "low"


def mark_disable_exports_when_needed(*, source_mode: str, citations: list[LegalSkillCitation], warnings: list[str]) -> bool:
    if source_mode == "strict" and not any(c.source_type in {"official", "internal"} for c in citations):
        return True
    return bool(warnings)


def build_reviewer_note(
    *,
    risk_level: str,
    source_mode: str,
    citations: list[LegalSkillCitation],
    warnings: list[str],
) -> LegalSkillReviewerNote:
    base = enforce_attorney_review_gate("", risk_level=risk_level)
    source_warnings = enforce_citation_policy(citations, source_mode=source_mode)
    reasons = [*base.reasons, *source_warnings, *warnings]
    blocks_export = mark_disable_exports_when_needed(source_mode=source_mode, citations=citations, warnings=[*source_warnings, *warnings])
    return LegalSkillReviewerNote(
        text="Bozza per revisione: valida fonti, contesto del fascicolo e strategia prima di procedere.",
        needs_review=True,
        blocks_export=blocks_export,
        reasons=sorted({item for item in reasons if item}),
    )


__all__ = [
    "build_reviewer_note",
    "classify_output_risk",
    "enforce_attorney_review_gate",
    "enforce_citation_policy",
    "enforce_jurisdiction_policy",
    "enforce_non_lawyer_gate",
    "enforce_privilege_destination_policy",
    "enforce_source_sufficiency",
    "mark_disable_exports_when_needed",
    "sanitize_untrusted_document_text",
]
