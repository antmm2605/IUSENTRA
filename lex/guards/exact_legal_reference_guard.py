"""Guardia exact-match per riferimenti legali specifici (sentenze, ordinanze).

Per sentenze specifiche (is_exact_reference=True):

Una fonte è exact_match solo se:
- contiene il numero richiesto
- contiene anno o data compatibile
- è su dominio ufficiale o fonte verificata
- il titolo o contenuto conferma il riferimento

Se manca numero o data → related_match, non exact_match.

Se ci sono N risultati ma solo uno è esatto → mostra solo quello come fonte principale.

Se nessuno è esatto:
- non dire "ho trovato"
- dire "non ho trovato conferma ufficiale esatta"
- elencare al massimo 2 risultati vicini come "possibili correlati"
- confidence max 0.45

Se esatto ma manca testo integrale/dispositivo:
- "fonte individuata, testo integrale/dispositivo non disponibile"
- confidence max 0.55

Se esatto con testo integrale:
- confidence può salire normalmente
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lex.contracts import GuardVerdict
from lex.research.case_law_reference_parser import ExactLegalReference


# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

CONFIDENCE_CAP_NOT_FOUND = 0.45
CONFIDENCE_CAP_FOUND_NO_TEXT = 0.55
CONFIDENCE_CAP_FOUND_WITH_TEXT = 0.85

_OFFICIAL_DOMAINS = frozenset({
    "cortedicassazione.it",
    "cortecostituzionale.it",
    "giustizia-amministrativa.it",
    "normattiva.it",
    "gazzettaufficiale.it",
    "eur-lex.europa.eu",
    "curia.europa.eu",
    "agenziaentrate.gov.it",
    "giustizia.it",
    "pst.giustizia.it",
})

_FULL_TEXT_MARKERS = (
    "dispositivo",
    "fatto e diritto",
    "in fatto",
    "in diritto",
    "p.q.m.",
    "per questi motivi",
    "il tribunale",
    "la corte",
    "osserva:",
    "rileva che",
    "svolgimento del processo",
    "motivi della decisione",
)


# ---------------------------------------------------------------------------
# Modelli
# ---------------------------------------------------------------------------

@dataclass
class ExactMatchResult:
    """Risultato della verifica exact match su una fonte."""

    is_exact_match: bool
    is_related_match: bool
    has_full_text: bool
    match_reason: str
    source_id: str
    source_title: str
    source_url: str
    source_domain: str
    is_official_domain: bool
    match_score: float             # 0.0 – 1.0


@dataclass
class ExactLegalReferenceGuardVerdict:
    """Verdict della guardia per riferimento legale esatto."""

    reference: ExactLegalReference
    exact_matches: list[ExactMatchResult]
    related_matches: list[ExactMatchResult]
    exact_match_found: bool
    full_text_available: bool
    confidence_cap: float
    confidence_cap_reason: str
    primary_source: dict[str, Any] | None
    related_sources: list[dict[str, Any]]
    warnings: list[str]
    missing_evidence: list[str]
    verdict: GuardVerdict
    debug_log: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Guardia principale
# ---------------------------------------------------------------------------

class ExactLegalReferenceGuard:
    """Filtra i risultati di ricerca per riferimenti legali esatti.

    Uso:
        guard = ExactLegalReferenceGuard()
        verdict = guard.check(reference=ref, evidence_items=items)
    """

    def check(
        self,
        *,
        reference: ExactLegalReference,
        evidence_items: list[dict[str, Any]],
    ) -> ExactLegalReferenceGuardVerdict:
        """Verifica i risultati di ricerca rispetto al riferimento esatto.

        Args:
            reference: Riferimento estratto dal parser (ExactLegalReference).
            evidence_items: Lista di item evidenza dal retrieval ({title, url, excerpt, text, ...}).

        Returns:
            ExactLegalReferenceGuardVerdict con classificazione completa.
        """
        debug: list[str] = []

        if not reference.is_exact_reference:
            # Non è un riferimento esatto — guard non applicabile
            guard_verdict = GuardVerdict(
                allowed=True,
                warnings=["ExactLegalReferenceGuard non applicabile: riferimento non esatto."],
                risk_level="low",
            )
            return ExactLegalReferenceGuardVerdict(
                reference=reference,
                exact_matches=[],
                related_matches=[],
                exact_match_found=False,
                full_text_available=False,
                confidence_cap=1.0,
                confidence_cap_reason="non applicabile",
                primary_source=None,
                related_sources=[],
                warnings=["Riferimento non esatto — guard non applicato."],
                missing_evidence=[],
                verdict=guard_verdict,
                debug_log=debug,
            )

        # ── Classificazione ogni item ──────────────────────────────────────
        exact_matches: list[ExactMatchResult] = []
        related_matches: list[ExactMatchResult] = []

        for item in evidence_items:
            result = _classify_item(item, reference, debug)
            if result.is_exact_match:
                exact_matches.append(result)
            elif result.is_related_match:
                related_matches.append(result)

        # Ordina per match_score decrescente
        exact_matches.sort(key=lambda x: x.match_score, reverse=True)
        related_matches.sort(key=lambda x: x.match_score, reverse=True)

        debug.append(
            f"exact_matches={len(exact_matches)} related_matches={len(related_matches)} "
            f"total_items={len(evidence_items)}"
        )

        # ── Verifica testo integrale ───────────────────────────────────────
        full_text_available = any(
            _has_full_text(item, reference) for item in evidence_items
            if _is_exact_by_content(item, reference)
        )

        # ── Confidence cap ─────────────────────────────────────────────────
        warnings: list[str] = []
        missing_evidence: list[str] = []

        if not exact_matches:
            confidence_cap = CONFIDENCE_CAP_NOT_FOUND
            cap_reason = (
                f"Nessuna corrispondenza esatta trovata per {reference.kind} "
                f"n. {reference.number}"
                + (f" del {reference.date}" if reference.date else "")
                + "."
            )
            warnings.append(
                f"Non trovata conferma ufficiale esatta di {reference.kind} "
                f"n. {reference.number}"
                + (f" del {reference.date}" if reference.date else "")
                + "."
            )
            missing_evidence.append(
                f"Testo della {reference.kind} n. {reference.number}"
                + (f"/{reference.year}" if reference.year else "")
                + " non trovato nelle fonti interrogate."
            )
        elif not full_text_available:
            confidence_cap = CONFIDENCE_CAP_FOUND_NO_TEXT
            cap_reason = (
                f"Fonte individuata per {reference.kind} n. {reference.number}, "
                "ma testo integrale/dispositivo non disponibile nelle evidenze."
            )
            warnings.append(
                "Fonte individuata, ma testo integrale/dispositivo non disponibile "
                "nelle evidenze. Verificare il link ufficiale."
            )
            missing_evidence.append("Testo integrale / dispositivo della sentenza.")
        else:
            confidence_cap = CONFIDENCE_CAP_FOUND_WITH_TEXT
            cap_reason = f"Fonte esatta trovata con testo per {reference.kind} n. {reference.number}."

        # ── Fonte principale e correlate ───────────────────────────────────
        primary_source: dict[str, Any] | None = None
        if exact_matches:
            best = exact_matches[0]
            primary_source = {
                "source_id": best.source_id,
                "title": best.source_title,
                "url": best.source_url,
                "domain": best.source_domain,
                "is_official": best.is_official_domain,
                "match_reason": best.match_reason,
                "has_full_text": best.has_full_text,
            }

        related_sources = [
            {
                "source_id": r.source_id,
                "title": r.source_title,
                "url": r.source_url,
                "domain": r.source_domain,
                "is_official": r.is_official_domain,
                "match_reason": r.match_reason,
            }
            for r in related_matches[:2]  # massimo 2 correlate
        ]

        # ── GuardVerdict ───────────────────────────────────────────────────
        if exact_matches:
            guard_verdict = GuardVerdict(
                allowed=True,
                warnings=warnings,
                risk_level="low" if full_text_available else "medium",
            )
        else:
            guard_verdict = GuardVerdict(
                allowed=True,
                warnings=warnings,
                risk_level="medium",
            )

        return ExactLegalReferenceGuardVerdict(
            reference=reference,
            exact_matches=exact_matches,
            related_matches=related_matches,
            exact_match_found=bool(exact_matches),
            full_text_available=full_text_available,
            confidence_cap=confidence_cap,
            confidence_cap_reason=cap_reason,
            primary_source=primary_source,
            related_sources=related_sources,
            warnings=warnings,
            missing_evidence=missing_evidence,
            verdict=guard_verdict,
            debug_log=debug,
        )


# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

def _text_of_item(item: dict[str, Any]) -> str:
    return " ".join([
        str(item.get("title") or ""),
        str(item.get("excerpt") or ""),
        str(item.get("text") or ""),
        str(item.get("content") or ""),
    ]).lower()


def _url_of_item(item: dict[str, Any]) -> str:
    return str(item.get("url") or item.get("source_url") or "").strip()


def _domain_of_item(item: dict[str, Any]) -> str:
    url = _url_of_item(item)
    if not url:
        return ""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _is_official(item: dict[str, Any]) -> bool:
    domain = _domain_of_item(item)
    for od in _OFFICIAL_DOMAINS:
        if domain == od or domain.endswith("." + od):
            return True
    return bool(
        str(item.get("authority") or "").lower() in ("official", "official_web", "cassazione")
        or str(item.get("trust_class") or "").upper() == "A"
        or item.get("verified_reference")
    )


def _contains_number(text: str, number: str) -> bool:
    if not number:
        return False
    import re
    # Cerca il numero come intero o con zeri
    patterns = [
        rf"\b{re.escape(number)}\b",
        rf"\bn\.\s*{re.escape(number)}\b",
        rf"/{re.escape(number)}\b",
        rf"\b{re.escape(number)}/",
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False


def _contains_year_or_date(text: str, year: str, date: str) -> bool:
    if year and year in text:
        return True
    if date:
        # Prova diverse rappresentazioni della data
        parts = date.replace("/", "-").replace(".", "-").split("-")
        if len(parts) == 3:
            day, month, yr = parts
            for sep in ("/", "-", "."):
                if f"{day}{sep}{month}{sep}{yr}" in text or f"{yr}{sep}{month}{sep}{day}" in text:
                    return True
        if year in text:
            return True
    return False


def _is_exact_by_content(item: dict[str, Any], ref: ExactLegalReference) -> bool:
    text = _text_of_item(item)
    return (
        _contains_number(text, ref.number)
        and _contains_year_or_date(text, ref.year, ref.date)
    )


def _has_full_text(item: dict[str, Any], ref: ExactLegalReference) -> bool:
    text = _text_of_item(item)
    if not _is_exact_by_content(item, ref):
        return False
    return any(marker in text for marker in _FULL_TEXT_MARKERS)


def _classify_item(
    item: dict[str, Any],
    ref: ExactLegalReference,
    debug: list[str],
) -> ExactMatchResult:
    text = _text_of_item(item)
    url = _url_of_item(item)
    domain = _domain_of_item(item)
    official = _is_official(item)
    title = str(item.get("title") or "")
    source_id = str(item.get("source_id") or item.get("id") or "")

    has_number = _contains_number(text, ref.number)
    has_year_date = _contains_year_or_date(text, ref.year, ref.date)
    has_full = _has_full_text(item, ref)

    # Exact match: numero + anno/data + dominio ufficiale O fonte verificata
    is_exact = has_number and has_year_date and (official or domain in _OFFICIAL_DOMAINS)
    # Related: ha numero o anno ma non tutto
    is_related = (has_number or has_year_date) and not is_exact

    match_score = 0.0
    if is_exact:
        match_score = 0.90
        if has_full:
            match_score = 1.0
        elif official:
            match_score = 0.95
    elif is_related:
        match_score = 0.3 if has_number else 0.2

    reason_parts = []
    if has_number:
        reason_parts.append(f"numero {ref.number} presente")
    if has_year_date:
        reason_parts.append(f"anno/data presente")
    if official:
        reason_parts.append("dominio ufficiale")
    if has_full:
        reason_parts.append("testo integrale/dispositivo")

    match_reason = "; ".join(reason_parts) if reason_parts else "nessuna corrispondenza"

    debug.append(
        f"item={title[:50]!r} exact={is_exact} related={is_related} "
        f"number={has_number} yeardate={has_year_date} official={official} score={match_score}"
    )

    return ExactMatchResult(
        is_exact_match=is_exact,
        is_related_match=is_related and not is_exact,
        has_full_text=has_full,
        match_reason=match_reason,
        source_id=source_id,
        source_title=title,
        source_url=url,
        source_domain=domain,
        is_official_domain=official,
        match_score=match_score,
    )


# ---------------------------------------------------------------------------
# Formatter risposta
# ---------------------------------------------------------------------------

def format_exact_reference_response(
    verdict: ExactLegalReferenceGuardVerdict,
) -> str:
    """Formatta la risposta italiana per una ricerca sentenza specifica.

    Caso A — trovata: fonte principale + avvertenze.
    Caso B — non trovata: comunicazione chiara + prossima azione.
    """
    ref = verdict.reference
    ref_label = f"{ref.kind.capitalize()} n. {ref.number}"
    if ref.date:
        ref_label += f" del {ref.date}"
    elif ref.year:
        ref_label += f"/{ref.year}"

    if verdict.exact_match_found and verdict.primary_source:
        ps = verdict.primary_source
        lines: list[str] = [
            f"Ho individuato la fonte ufficiale della pronuncia richiesta.",
            "",
            f"**{ref_label}**",
        ]
        if ps.get("is_official"):
            lines.append(f"Fonte: {ps.get('domain', 'fonte ufficiale')}")
        if ps.get("url"):
            lines.append(f"Link ufficiale: {ps['url']}")
        if ps.get("match_reason"):
            lines.append(f"Corrispondenza: {ps['match_reason']}")
        lines.append("")
        if not verdict.full_text_available:
            lines.append(
                "**Nota**: testo integrale / dispositivo non disponibile nelle evidenze. "
                "Prima di citare in atto o parere, acquisire il testo integrale dal link ufficiale."
            )
        if verdict.related_sources:
            lines.append("")
            lines.append("Possibili pronunce correlate (non coincidenti con il riferimento richiesto):")
            for rs in verdict.related_sources[:2]:
                lines.append(f"- {rs.get('title', 'titolo n.d.')} ({rs.get('domain', '')})")
        lines.append("")
        lines.append(f"Fonti: {ps.get('domain', 'fonte ufficiale individuata')}.")
        return "\n".join(lines)

    # Caso B — non trovata
    searched = ["Corte di Cassazione"]
    if ref.court and ref.court not in searched:
        searched.append(ref.court)

    lines = [
        f"Non ho trovato una conferma ufficiale esatta della {ref_label} nelle fonti interrogate.",
        "",
        "Ho cercato su:",
    ]
    for s in searched:
        lines.append(f"- {s}")
    lines.append("")
    lines.append(
        "Non considero sufficienti risultati generici o sentenze con numero/data diversi."
    )
    if verdict.related_sources:
        lines.append("")
        lines.append("Risultati correlati trovati (potrebbero non corrispondere):")
        for rs in verdict.related_sources[:2]:
            lines.append(f"- {rs.get('title', 'titolo n.d.')} ({rs.get('domain', '')})")
    lines.append("")
    lines.append(
        "**Prossima azione**: verificare manualmente sul portale ufficiale "
        "(es. Cassazione → www.cortedicassazione.it) o caricare il link/documento se disponibile."
    )
    return "\n".join(lines)
