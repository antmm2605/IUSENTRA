from __future__ import annotations

import re
from typing import Any


CODE_ARTICLE_RE = re.compile(
    r"\b(?P<code>cod\.?\s+proc\.?\s+pen\.?|cod\.?\s+proc\.?\s+civ\.?|cod\.?\s+pen\.?|cod\.?\s+civ\.?|"
    r"codice\s+di\s+procedura\s+penale|codice\s+di\s+procedura\s+civile|codice\s+penale|codice\s+civile|"
    r"codice\s+della\s+strada|c\.p\.p\.|c\.p\.c\.|c\.p\.|c\.c\.|c\.d\.s\.)\s+"
    r"(?P<article>artt?\.?\s+[0-9][A-Za-z0-9_.-]*(?:\s*(?:,|e)\s*[0-9][A-Za-z0-9_.-]*)?)",
    re.IGNORECASE,
)
ARTICLE_RE = re.compile(
    r"\b(?:artt?\.?|articoli?)\s+[0-9][A-Za-z0-9_.-]*"
    r"(?:\s*(?:,|e)\s*[0-9][A-Za-z0-9_.-]*)?"
    r"(?:\s*,?\s*(?:comma|commi)\s+(?:[0-9]+|primo|secondo|terzo|quarto|quinto|sesto|settimo|ottavo|nono|decimo)"
    r"(?:\s*(?:,|e)\s*(?:[0-9]+|primo|secondo|terzo|quarto|quinto|sesto|settimo|ottavo|nono|decimo))?)?"
    r"(?:\s*(?:c\.p\.p\.|c\.p\.c\.|c\.p\.|c\.c\.|c\.d\.s\.|cod\.?\s+proc\.?\s+pen\.?|cod\.?\s+proc\.?\s+civ\.?|"
    r"cod\.?\s+pen\.?|cod\.?\s+civ\.?|codice\s+di\s+procedura\s+penale|codice\s+di\s+procedura\s+civile|"
    r"codice\s+penale|codice\s+civile|codice\s+della\s+strada))?",
    re.IGNORECASE,
)
ACT_RE = re.compile(
    r"\b(?:D\.?\s*Lgs\.?|Decreto\s+legislativo|D\.?\s*L\.?|Decreto-?legge|D\.?\s*P\.?\s*R\.?|"
    r"D\.?\s*M\.?|Legge|L\.)\s*(?:\d{1,2}\s+[A-Za-zàèéìòù]+\s+\d{4},?\s*)?"
    r"(?:n\.?\s*)?[0-9]{1,6}(?:/[0-9]{2,4})?",
    re.IGNORECASE,
)
EU_ACT_RE = re.compile(r"\b(?:Regolamento|Direttiva)\s+\(?UE\)?\s+[0-9]{4}/[0-9]{1,6}", re.IGNORECASE)
CELEX_RE = re.compile(r"\b(?:CELEX[:\s]*)?(?P<celex>[0-9][0-9]{4}[A-Z]{1,3}[0-9]{3,4})\b", re.IGNORECASE)
EU_CASE_RE = re.compile(r"\b(?:causa\s+)?(?:C|T|F)-[0-9]{1,5}/[0-9]{2,4}\b", re.IGNORECASE)
COURT_RE = re.compile(
    r"\b(?:Corte\s+Suprema\s+di\s+Cassazione|Corte\s+di\s+Cassazione|Cassazione|Corte\s+costituzionale|"
    r"Consiglio\s+di\s+Stato|TAR(?:\s+[A-Za-zàèéìòù]+)?|CGUE|Corte\s+di\s+giustizia\s+UE|CEDU|Corte\s+EDU)\b",
    re.IGNORECASE,
)
DECISION_RE = re.compile(
    r"\b(?:sentenza|ordinanza|decreto|delibera|decisione|parere)\s+(?:n\.?\s*)?[0-9]{1,6}(?:/[0-9]{2,4})?"
    r"(?:\s+del\s+\d{1,2}(?:/\d{1,2}/\d{2,4}|\s+[A-Za-zàèéìòù]+\s+\d{4}))?",
    re.IGNORECASE,
)
RG_RE = re.compile(
    r"\b(?:R\.?\s*G\.?|RG|ricorso\s+n\.?|ricorso\s+nr\.?)\s*(?:n\.?\s*)?[0-9]{1,6}\s*/\s*[0-9]{2,4}\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"\b(?:[0-3]?\d/[01]?\d/[12]\d{3}|[0-3]?\d\s+[A-Za-zàèéìòù]+\s+[12]\d{3})\b", re.IGNORECASE)
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
CONTENT_ID_RE = re.compile(r"\bcontentId=[A-Za-z0-9_-]+\b", re.IGNORECASE)


def clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def extract_references(
    text: Any,
    *,
    source_url: Any = "",
    attachment_url: Any = "",
    source_document: Any = "",
    document_part: Any = "",
    limit: int = 64,
) -> list[dict[str, Any]]:
    source = clean_spaces(text)
    if not source:
        return []
    refs: list[dict[str, Any]] = []
    for match in CODE_ARTICLE_RE.finditer(source):
        value = f"{clean_spaces(match.group('article'))} {clean_spaces(match.group('code'))}"
        _append_reference(
            refs,
            source,
            match.start(),
            match.end(),
            reference_type="article",
            confidence=0.92,
            source_url=source_url or source_document,
            attachment_url=attachment_url,
            document_part=document_part,
            override_text=value,
        )
    for pattern, reference_type, confidence in (
        (ARTICLE_RE, "article", 0.9),
        (ACT_RE, "act", 0.88),
        (EU_ACT_RE, "eu_act", 0.88),
        (CELEX_RE, "celex", 0.91),
        (EU_CASE_RE, "eu_case", 0.86),
        (COURT_RE, "court", 0.76),
        (DECISION_RE, "decision", 0.86),
        (RG_RE, "rg", 0.9),
        (DATE_RE, "date", 0.72),
        (YEAR_RE, "year", 0.62),
        (CONTENT_ID_RE, "content_id", 0.88),
    ):
        for match in pattern.finditer(source):
            _append_reference(
                refs,
                source,
                match.start(),
                match.end(),
                reference_type=reference_type,
                confidence=confidence,
                source_url=source_url or source_document,
                attachment_url=attachment_url,
                document_part=document_part,
            )
    return _dedupe(refs, limit=limit)


def compat_references(
    text: Any,
    *,
    source_document: Any = "",
    document_part: Any = "",
    limit: int = 48,
) -> list[dict[str, Any]]:
    rows = extract_references(
        text,
        source_url=source_document,
        source_document=source_document,
        document_part=document_part,
        limit=limit,
    )
    return [
        {
            "text": row["raw_text"],
            "normalized_text": row["normalized_text"],
            "type": row["reference_type"],
            "context_snippet": row["snippet"],
            "source_document": clean_spaces(source_document),
            "document_part": clean_spaces(document_part),
            "confidence": row["confidence"],
            "official_url": "",
            "raw_text": row["raw_text"],
            "reference_type": row["reference_type"],
            "snippet": row["snippet"],
            "source_url": row["source_url"],
            "attachment_url": row["attachment_url"],
        }
        for row in rows
    ]


def reference_labels(
    references: list[dict[str, Any]],
    *,
    allowed_types: tuple[str, ...] = (),
    limit: int = 20,
) -> list[str]:
    allowed = {str(item) for item in allowed_types}
    labels: list[str] = []
    seen: set[str] = set()
    for row in references:
        row_type = str(row.get("reference_type") or row.get("type") or "")
        if allowed and row_type not in allowed:
            continue
        label = clean_spaces(row.get("normalized_text") or row.get("raw_text") or row.get("text"))
        key = label.casefold()
        if not label or key in seen:
            continue
        seen.add(key)
        labels.append(label)
        if len(labels) >= limit:
            break
    return labels


def _append_reference(
    refs: list[dict[str, Any]],
    source: str,
    start: int,
    end: int,
    *,
    reference_type: str,
    confidence: float,
    source_url: Any,
    attachment_url: Any,
    document_part: Any,
    override_text: str = "",
) -> None:
    raw = clean_spaces(override_text or source[start:end]).strip(" ,;:")
    if not raw:
        return
    refs.append(
        {
            "raw_text": raw,
            "normalized_text": _normalize_reference(raw),
            "reference_type": reference_type,
            "snippet": _snippet(source, start, end),
            "source_url": clean_spaces(source_url),
            "attachment_url": clean_spaces(attachment_url),
            "document_part": clean_spaces(document_part),
            "confidence": round(float(confidence), 2),
            "official_url": "",
        }
    )


def _normalize_reference(value: str) -> str:
    text = clean_spaces(value)
    celex_match = re.fullmatch(r"(?:CELEX[:\s]*)?([0-9][0-9]{4}[A-Z]{1,3}[0-9]{3,4})", text, flags=re.IGNORECASE)
    if celex_match:
        return f"CELEX:{celex_match.group(1).upper()}"
    text = re.sub(r"\barticoli\b", "artt.", text, flags=re.IGNORECASE)
    text = re.sub(r"\barticolo\b", "art.", text, flags=re.IGNORECASE)
    text = re.sub(r"\bartt\b(?!\.)", "artt.", text, flags=re.IGNORECASE)
    text = re.sub(r"\bart\b(?!\.)", "art.", text, flags=re.IGNORECASE)
    fixes = {
        r"\bcod\.?\s+proc\.?\s+pen\.?\b": "c.p.p.",
        r"\bcodice\s+di\s+procedura\s+penale\b": "c.p.p.",
        r"\bcod\.?\s+proc\.?\s+civ\.?\b": "c.p.c.",
        r"\bcodice\s+di\s+procedura\s+civile\b": "c.p.c.",
        r"\bcod\.?\s+pen\.?\b": "c.p.",
        r"\bcodice\s+penale\b": "c.p.",
        r"\bcod\.?\s+civ\.?\b": "c.c.",
        r"\bcodice\s+civile\b": "c.c.",
        r"\bcodice\s+della\s+strada\b": "c.d.s.",
        r"\bdecreto\s+legislativo\b": "D.Lgs.",
        r"\bdecreto-?legge\b": "D.L.",
        r"\blegge\b": "L.",
    }
    for pattern, replacement in fixes.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _snippet(source: str, start: int, end: int, *, radius: int = 110) -> str:
    left = max(0, start - radius)
    right = min(len(source), end + radius)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(source) else ""
    return clean_spaces(prefix + source[left:right] + suffix)


def _dedupe(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        key = (
            str(row.get("reference_type") or ""),
            clean_spaces(row.get("normalized_text")).casefold(),
            clean_spaces(row.get("attachment_url")),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
        if len(output) >= max(1, int(limit or 1)):
            break
    return output
