"""Estrazione citazioni giuridiche per l'apprendimento di Lex (facciata + estensione).

Riusa l'estrattore deterministico di produzione `pct.legal_reference_extractor`
(articoli+codici, atti, atti UE, CELEX, cause UE, corti, decisioni) e lo estende
con gli **atti nominati** che quel modulo non copre ancora: "GDPR" nudo,
"art. 6 GDPR", "codice privacy". L'estensione vive QUI e non tocca il modulo pct
(usato in produzione dal presidio PEC): l'upstreaming è tracciato come
ImprovementProposal del ciclo autonomo, con regressioni PEC dedicate.

Gli offset `start`/`end` sono calcolati sul testo NORMALIZZATO (`clean_spaces`,
la stessa normalizzazione dell'estrattore pct); per le righe pct — che non
espongono posizioni — l'offset è la prima occorrenza del testo grezzo.
"""

from __future__ import annotations

import re

from pct.legal_reference_extractor import clean_spaces, extract_references

from lex.learning.models import LegalCitation

# Alias deterministici nome comune → (testo normalizzato, reference_type).
NAMED_ACT_ALIASES: dict[str, tuple[str, str]] = {
    "regolamento generale sulla protezione dei dati": ("Regolamento (UE) 2016/679", "eu_act"),
    "codice in materia di protezione dei dati personali": ("D.Lgs. 196/2003", "act"),
    "codice privacy": ("D.Lgs. 196/2003", "act"),
    "gdpr": ("Regolamento (UE) 2016/679", "eu_act"),
}
_NAMED_ACT_CONFIDENCE = 0.9

_NAMED_ACT_RE = re.compile(
    r"\b(?P<alias>" + "|".join(re.escape(alias) for alias in NAMED_ACT_ALIASES) + r")\b",
    re.IGNORECASE,
)
# "art. 6 GDPR", "artt. 13 e 14 del GDPR", "articolo 6, par. 1 Reg. (UE) 2016/679".
_ART_NAMED_ACT_RE = re.compile(
    r"\b(?:artt?\.?|articol[oi])\s+(?P<num>[0-9][0-9A-Za-z.\-]*(?:\s*(?:,|e)\s*[0-9][0-9A-Za-z.\-]*)?)"
    r"(?:\s*,?\s*(?:par\.|paragrafo|comma)\s*[0-9]+)?"
    r"\s*(?:,?\s*(?:del|della|dello)\s+)?"
    r"(?P<act>GDPR|Reg(?:olamento)?\.?\s*\(?\s*UE\s*\)?\s*(?:n\.?\s*)?2016/679)",
    re.IGNORECASE,
)


def extract_citations(text: str, *, source_url: str = "", limit: int = 64) -> list[LegalCitation]:
    """Estrae le citazioni dal testo: righe pct + atti nominati, dedup e offset."""

    source = clean_spaces(text)
    if not source:
        return []

    enriched: list[LegalCitation] = []
    covered_spans: list[tuple[int, int]] = []
    for match in _ART_NAMED_ACT_RE.finditer(source):
        numero = clean_spaces(match.group("num")).strip(" ,;:")
        enriched.append(
            LegalCitation(
                raw_text=clean_spaces(match.group(0)),
                normalized_text=f"art. {numero} Regolamento (UE) 2016/679",
                reference_type="article",
                confidence=_NAMED_ACT_CONFIDENCE,
                start=match.start(),
                end=match.end(),
                snippet=_snippet(source, match.start(), match.end()),
                source_url=source_url,
            )
        )
        covered_spans.append((match.start(), match.end()))
    for match in _NAMED_ACT_RE.finditer(source):
        if _inside_any(match.start(), match.end(), covered_spans):
            continue
        normalized, reference_type = NAMED_ACT_ALIASES[match.group("alias").casefold()]
        enriched.append(
            LegalCitation(
                raw_text=clean_spaces(match.group(0)),
                normalized_text=normalized,
                reference_type=reference_type,
                confidence=_NAMED_ACT_CONFIDENCE,
                start=match.start(),
                end=match.end(),
                snippet=_snippet(source, match.start(), match.end()),
                source_url=source_url,
            )
        )

    citations = list(enriched)
    for row in extract_references(source, source_url=source_url, limit=limit):
        raw = str(row.get("raw_text") or "")
        start = source.find(raw)
        end = start + len(raw) if start >= 0 else -1
        # Una riga "nuda" (es. "art. 6" dentro "art. 6 GDPR") il cui span è
        # contenuto in una citazione arricchita è ridondante: si sopprime.
        if start >= 0 and _inside_any(start, end, [(c.start, c.end) for c in enriched]):
            continue
        citations.append(
            LegalCitation(
                raw_text=raw,
                normalized_text=str(row.get("normalized_text") or raw),
                reference_type=str(row.get("reference_type") or "unknown"),
                confidence=float(row.get("confidence") or 0.0),
                start=start,
                end=end,
                snippet=str(row.get("snippet") or ""),
                source_url=str(row.get("source_url") or source_url),
                official_url=str(row.get("official_url") or ""),
            )
        )

    return _dedupe(citations, limit=limit)


def _inside_any(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start >= span_start and end <= span_end for span_start, span_end in spans)


def _snippet(source: str, start: int, end: int, *, radius: int = 110) -> str:
    left = max(0, start - radius)
    right = min(len(source), end + radius)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(source) else ""
    return clean_spaces(prefix + source[left:right] + suffix)


def _dedupe(citations: list[LegalCitation], *, limit: int) -> list[LegalCitation]:
    best: dict[tuple[str, str], LegalCitation] = {}
    for citation in citations:
        key = (citation.reference_type, citation.normalized_text.casefold())
        current = best.get(key)
        if current is None or citation.confidence > current.confidence:
            best[key] = citation
    ordered = sorted(best.values(), key=lambda item: (item.start if item.start >= 0 else 10**9, item.normalized_text))
    return ordered[: max(1, int(limit or 1))]


__all__ = ["NAMED_ACT_ALIASES", "extract_citations"]
