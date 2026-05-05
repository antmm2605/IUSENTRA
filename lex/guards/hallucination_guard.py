"""Guardia anti allucinazione per Lex."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from lex.contracts import GuardVerdict


_STRICT_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}


@dataclass(frozen=True, slots=True)
class _LegalReference:
    kind: str
    key: str
    label: str


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize(value: Any) -> str:
    text = _clean(value).lower()
    return (
        text.replace("codice civile", "c.c.")
        .replace("codice di procedura civile", "c.p.c.")
        .replace("codice procedura civile", "c.p.c.")
        .replace("codice penale", "c.p.")
        .replace("codice di procedura penale", "c.p.p.")
        .replace("decreto legislativo", "d.lgs.")
        .replace("decreto ministeriale", "d.m.")
    )


def _add_reference(refs: list[_LegalReference], kind: str, key: str, label: str) -> None:
    clean_key = _normalize(key)
    if not clean_key:
        return
    ref = _LegalReference(kind=kind, key=clean_key, label=_clean(label) or clean_key)
    if ref not in refs:
        refs.append(ref)


def extract_legal_references(text: Any) -> list[_LegalReference]:
    """Estrae riferimenti giuridici specifici senza dipendere da stringhe identiche."""

    normalized = _normalize(text)
    if not normalized:
        return []

    refs: list[_LegalReference] = []
    authority_pattern = (
        r"(cassazione|corte costituzionale|consiglio di stato|tar(?:\s+[a-z]+)?)"
        r"[^.\n;]{0,80}?(?:sentenza|ordinanza|pronuncia)?\s*(?:n\.|numero)\s*(\d{1,7})(?:\s*/\s*|\s+del\s+)?(\d{4})?"
    )
    for match in re.finditer(authority_pattern, normalized):
        authority, number, year = match.groups()
        key = f"{authority}:{number}:{year or ''}"
        _add_reference(refs, "case_law", key, match.group(0))

    for match in re.finditer(r"\bsentenza\s+(?:n\.|numero)\s*(\d{1,7})(?:\s*/\s*|\s+del\s+)(\d{4})", normalized):
        number, year = match.groups()
        _add_reference(refs, "case_law", f"sentenza:{number}:{year}", match.group(0))

    for match in re.finditer(r"\becli:[a-z0-9:.]+", normalized):
        _add_reference(refs, "ecli", match.group(0), match.group(0))

    article_pattern = (
        r"\bart\.?\s*(\d+[a-z]*(?:[-/]\w+)?)"
        r"(?:\s*(?:,|del|della|del\s+codice)?\s*)"
        r"(c\.c\.|c\.p\.c\.|c\.p\.|c\.p\.p\.|cost\.)?"
    )
    for match in re.finditer(article_pattern, normalized):
        article, code = match.groups()
        code_key = code or ""
        _add_reference(refs, "article", f"art:{article}:{code_key}", match.group(0))

    normative_patterns = (
        ("legge", r"\blegge\s+(?:n\.|numero)\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
        ("d_lgs", r"\bd\.lgs\.?\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
        ("d_m", r"\bd\.m\.?\s*(?:n\.|numero)?\s*(\d{1,5})(?:\s*/\s*|\s+del\s+)(\d{4})"),
    )
    for kind, pattern in normative_patterns:
        for match in re.finditer(pattern, normalized):
            number, year = match.groups()
            _add_reference(refs, kind, f"{kind}:{number}:{year}", match.group(0))

    return refs


def _text_from_row(row: Any) -> str:
    if isinstance(row, dict):
        metadata = dict(row.get("metadata") or {})
        return " ".join(
            _clean(value)
            for value in (
                row.get("title"),
                row.get("content"),
                row.get("excerpt"),
                row.get("text"),
                row.get("citation"),
                row.get("official_url"),
                row.get("url"),
                metadata.get("ecli"),
                metadata.get("numero_sentenza"),
                metadata.get("anno_sentenza"),
                metadata.get("numero_provvedimento"),
                metadata.get("anno"),
            )
            if _clean(value)
        )
    metadata = dict(getattr(row, "metadata", {}) or {})
    return " ".join(
        _clean(value)
        for value in (
            getattr(row, "title", ""),
            getattr(row, "content", ""),
            getattr(row, "excerpt", ""),
            getattr(row, "official_url", ""),
            metadata.get("ecli"),
            metadata.get("numero_sentenza"),
            metadata.get("anno_sentenza"),
            metadata.get("numero_provvedimento"),
            metadata.get("anno"),
        )
        if _clean(value)
    )


def _evidence_rows(evidence: Any) -> list[Any]:
    if isinstance(evidence, dict):
        return [*list(evidence.get("items") or []), *list(evidence.get("citations") or [])]
    return [*list(getattr(evidence, "items", []) or []), *list(getattr(evidence, "citations", []) or [])]


def _supported_by_evidence(ref: _LegalReference, evidence_refs: Iterable[_LegalReference]) -> bool:
    refs = list(evidence_refs or [])
    if ref in refs:
        return True
    for candidate in refs:
        if candidate.kind == ref.kind and candidate.key == ref.key:
            return True
        if ref.kind == "article" and candidate.kind == "article":
            ref_parts = ref.key.split(":")
            candidate_parts = candidate.key.split(":")
            if len(ref_parts) >= 2 and len(candidate_parts) >= 2 and ref_parts[1] == candidate_parts[1]:
                ref_code = ref_parts[2] if len(ref_parts) > 2 else ""
                candidate_code = candidate_parts[2] if len(candidate_parts) > 2 else ""
                if not ref_code or not candidate_code or ref_code == candidate_code:
                    return True
        if ref.kind == "case_law" and candidate.kind == "case_law":
            ref_parts = [part for part in ref.key.split(":") if part]
            candidate_parts = [part for part in candidate.key.split(":") if part]
            if len(ref_parts) >= 2 and len(candidate_parts) >= 2:
                if ref_parts[-2:] == candidate_parts[-2:]:
                    return True
    return False


class HallucinationGuard:
    def check(self, **kwargs):
        workflow = str(kwargs.get("workflow") or "")
        evidence = kwargs.get("evidence") or {}
        draft = kwargs.get("draft")
        draft_text = str(getattr(draft, "text", "") or "").strip()
        if not draft_text:
            return GuardVerdict(allowed=False, reasons=["Empty provider draft"], risk_level="high")

        draft_refs = extract_legal_references(draft_text)
        if not draft_refs:
            return GuardVerdict(allowed=True)

        rows = _evidence_rows(evidence)
        evidence_refs: list[_LegalReference] = []
        for row in rows:
            evidence_refs.extend(extract_legal_references(_text_from_row(row)))

        strict = workflow in _STRICT_WORKFLOWS
        if strict and not rows:
            return GuardVerdict(
                allowed=False,
                warnings=["La bozza contiene riferimenti giuridici specifici senza evidenze."],
                reasons=["Workflow strict con riferimenti normativi/giurisprudenziali non fondati."],
                risk_level="high",
            )

        missing = [ref for ref in draft_refs if not _supported_by_evidence(ref, evidence_refs)]
        if strict and missing:
            labels = ", ".join(ref.label for ref in missing[:4])
            return GuardVerdict(
                allowed=False,
                warnings=[f"Riferimenti giuridici non presenti nelle evidenze: {labels}."],
                reasons=["La bozza contiene estremi normativi o giurisprudenziali non supportati dal pacchetto evidenze."],
                risk_level="high",
            )

        if missing:
            labels = ", ".join(ref.label for ref in missing[:4])
            return GuardVerdict(
                allowed=True,
                warnings=[f"Riferimenti giuridici da verificare prima dell'uso: {labels}."],
                reasons=["Riferimenti rilevati nella bozza non allineati alle evidenze disponibili."],
                risk_level="medium",
            )
        return GuardVerdict(allowed=True)


__all__ = ["HallucinationGuard", "extract_legal_references"]
