from __future__ import annotations

import re
from typing import Any, Iterable

from lex.contracts import GuardVerdict, answer_contract_for


_CASE_LAW_PATTERNS: tuple[str, ...] = (
    r"\bsentenza\b",
    r"\bsentenze\b",
    r"\bgiurisprudenza\b",
    r"\bmassima\b",
    r"\bpronuncia\b",
    r"\bpronunce\b",
    r"\bcassazione\b",
    r"\bcorte costituzionale\b",
    r"\btribunale\b",
    r"\bcorte d(?:'|’)appello\b",
    r"\btar\b",
    r"\bconsiglio di stato\b",
)

_PDF_DOWNLOAD_PATTERNS: tuple[str, ...] = (
    r"\bpdf\b",
    r"\bscaric[a-z]*\b",
    r"\bdownload\b",
    r"\blink ufficiale\b",
    r"\btesto integrale\b",
)

_EXACT_REFERENCE_PATTERNS: tuple[str, ...] = (
    r"\bn\.\s*\d+",
    r"\bsez\.\s*[ivx0-9]+",
    r"\becli\b",
    r"\bmassimario\b",
)

_STRICT_WORKFLOWS = {"normativa", "giurisprudenza", "prassi", "research", "fonti"}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: str) -> str:
    return _clean_spaces(value).lower()


def is_case_law_lookup(text: str) -> bool:
    haystack = _normalize_text(text)
    return bool(haystack) and any(re.search(pattern, haystack) for pattern in _CASE_LAW_PATTERNS)


def is_pdf_download_request(text: str) -> bool:
    haystack = _normalize_text(text)
    return bool(haystack) and any(re.search(pattern, haystack) for pattern in _PDF_DOWNLOAD_PATTERNS)


def is_exact_reference_request(text: str) -> bool:
    haystack = _normalize_text(text)
    return bool(haystack) and any(re.search(pattern, haystack) for pattern in _EXACT_REFERENCE_PATTERNS)


def _evidence_items(evidence: Any) -> list[dict[str, Any]]:
    if isinstance(evidence, dict):
        items = evidence.get("items") or []
        citations = evidence.get("citations") or []
    else:
        items = getattr(evidence, "items", None) or []
        citations = getattr(evidence, "citations", None) or []
    rows: list[dict[str, Any]] = []
    for item in list(items):
        if isinstance(item, dict):
            rows.append(dict(item))
        else:
            rows.append(
                {
                    "source_type": getattr(item, "source_type", ""),
                    "source_id": getattr(item, "source_id", ""),
                    "title": getattr(item, "title", ""),
                    "text": getattr(item, "content", ""),
                    "score": getattr(item, "score", 0.0),
                    "trust_class": getattr(item, "trust_class", ""),
                    "source_level": getattr(item, "source_level", 0),
                    "verified_reference": getattr(item, "verified_reference", False),
                    "authority": getattr(item, "authority", ""),
                    "official_url": getattr(item, "official_url", None),
                    "published_at": getattr(item, "published_at", None),
                    "metadata": getattr(item, "metadata", {}) or {},
                }
            )
    for citation in list(citations):
        if isinstance(citation, dict):
            rows.append(dict(citation))
        else:
            rows.append(
                {
                    "source_type": getattr(citation, "source_type", ""),
                    "source_id": getattr(citation, "source_id", ""),
                    "title": getattr(citation, "title", ""),
                    "text": getattr(citation, "excerpt", ""),
                    "confidence": getattr(citation, "confidence", 0.0),
                    "authority": getattr(citation, "authority", ""),
                    "url": getattr(citation, "url", None),
                    "trust_class": getattr(citation, "trust_class", ""),
                    "source_level": getattr(citation, "source_level", 0),
                    "verified_reference": getattr(citation, "verified_reference", False),
                    "published_at": getattr(citation, "published_at", None),
                }
            )
    return rows


def has_verified_legal_reference(source: dict[str, Any]) -> bool:
    if bool(source.get("verified_reference")):
        return True

    metadata = dict(source.get("metadata") or {})
    verification_state = _normalize_text(
        source.get("stato_verifica_fonte")
        or source.get("stato_verifica")
        or metadata.get("stato_verifica_fonte")
        or metadata.get("stato_verifica")
    )
    ecli = _clean_spaces(source.get("ecli") or metadata.get("ecli"))
    organo = _clean_spaces(source.get("organo_giudicante") or metadata.get("organo_giudicante"))
    numero = _clean_spaces(
        source.get("numero_sentenza")
        or source.get("numero_provvedimento")
        or metadata.get("numero_sentenza")
        or metadata.get("numero_provvedimento")
    )
    anno = _clean_spaces(source.get("anno_sentenza") or source.get("anno") or metadata.get("anno"))
    title = _clean_spaces(source.get("title"))
    citation = _clean_spaces(source.get("citation"))
    official = _clean_spaces(
        source.get("official_url")
        or source.get("url_pagina_ufficiale")
        or source.get("url_pdf_ufficiale")
        or source.get("final_url")
        or source.get("url")
        or metadata.get("official_url")
        or metadata.get("url")
    )
    trust_class = _normalize_text(source.get("trust_class") or metadata.get("trust_class"))
    source_level = int(source.get("source_level") or metadata.get("source_level") or 0)

    if verification_state in {"verificata", "parzialmente_verificata"} and (official or ecli or (organo and numero and anno)):
        return True
    if trust_class == "a" and (official or ecli or (organo and numero and anno)):
        return True
    if source_level >= 1 and (official or ecli):
        return True
    return bool((title or citation) and official)


def collect_verified_legal_references(sources: Iterable[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(row) for row in list(sources or []) if has_verified_legal_reference(dict(row or {}))]


def has_verified_pdf_reference(sources: Iterable[dict[str, Any]] | None) -> bool:
    for row in collect_verified_legal_references(sources):
        metadata = dict(row.get("metadata") or {})
        final_url = _normalize_text(row.get("final_url") or row.get("url") or row.get("official_url"))
        kind = _normalize_text(row.get("kind") or metadata.get("kind"))
        direct_pdf = _normalize_text(row.get("url_pdf_ufficiale") or metadata.get("url_pdf_ufficiale"))
        if (
            bool(row.get("downloadable_pdf"))
            or bool(row.get("pdf_ufficiale_presente"))
            or bool(metadata.get("downloadable_pdf"))
            or kind == "pdf"
            or final_url.endswith(".pdf")
            or direct_pdf.endswith(".pdf")
        ):
            return True
    return False


def build_case_law_guard_prompt(question: str, sources: list[dict[str, Any]] | None) -> str:
    clean_question = _clean_spaces(question)
    verified = collect_verified_legal_references(sources)
    lines: list[str] = []

    if is_case_law_lookup(clean_question) and not verified:
        lines.extend(
            [
                "Affidabilita' legale: non hai ancora una pronuncia verificata da citare con numero, sezione, organo giudicante o PDF.",
                "Non inventare mai estremi specifici di sentenze, numeri di pronuncia, sezioni, tribunali o link PDF se non risultano da una fonte verificata.",
                "Se manca una fonte confermata, usa formule come: 'Non ho ancora una pronuncia verificata da citare con numero e PDF.' oppure 'Posso cercare una pronuncia reale e riportarti il link corretto.'.",
                "Non usare esempi fittizi presentandoli come sentenze reali.",
            ]
        )

    if is_pdf_download_request(clean_question) and not has_verified_pdf_reference(sources):
        lines.append(
            "Su richieste di PDF o download di pronunce: se il riferimento non e' verificato o non hai un PDF ufficiale, dillo chiaramente e non promettere scaricamenti inesistenti."
        )

    return "\n".join(lines).strip()


def build_unverified_pdf_reply(question: str, sources: list[dict[str, Any]] | None) -> str:
    clean_question = _clean_spaces(question)
    if not is_pdf_download_request(clean_question):
        return ""
    if not is_case_law_lookup(clean_question):
        return ""
    if has_verified_pdf_reference(sources):
        return ""
    if collect_verified_legal_references(sources):
        return (
            "Non vedo ancora un PDF ufficiale diretto da scaricare. "
            "Posso pero' cercare il link corretto della pronuncia verificata."
        )
    return (
        "Quel riferimento non e' ancora verificato come pronuncia reale, quindi non posso scaricarne il PDF. "
        "Posso invece cercare una sentenza reale e riportarti il link ufficiale."
    )


class LegalReferenceGuard:
    def check(self, **kwargs):
        request = kwargs.get("request")
        workflow = str(kwargs.get("workflow") or "")
        evidence = kwargs.get("evidence") or {}
        draft = kwargs.get("draft")
        question = _clean_spaces(getattr(request, "query", "") or "")
        rows = _evidence_items(evidence)
        verified = collect_verified_legal_references(rows)
        has_pdf = has_verified_pdf_reference(rows)
        contract = answer_contract_for(workflow) if workflow else answer_contract_for("chat")

        warnings: list[str] = []
        reasons: list[str] = []
        risk_level = "low"

        if contract.require_official_sources and not verified:
            warnings.append("Non risultano ancora riferimenti ufficiali verificati per il workflow richiesto.")
            reasons.append("Mancano fonti ufficiali o verifiche sufficienti per sostenere la risposta.")
            risk_level = "high"

        if workflow in _STRICT_WORKFLOWS and not rows:
            return GuardVerdict(
                allowed=False,
                warnings=["Nessuna evidenza disponibile per una risposta legale strutturata."],
                reasons=["Il workflow richiede retrieval e confronto fonti, ma il pacchetto evidenze e' vuoto."],
                risk_level="high",
            )

        if is_case_law_lookup(question) and not verified:
            return GuardVerdict(
                allowed=False,
                warnings=[
                    "Riferimento giurisprudenziale non verificato: Lex non deve inventare estremi o numeri di pronuncia."
                ],
                reasons=[
                    "La richiesta contiene lookup giurisprudenziale ma le evidenze non includono riferimenti verificati."
                ],
                risk_level="high",
            )

        if is_exact_reference_request(question) and not verified:
            return GuardVerdict(
                allowed=False,
                warnings=["Richiesta di riferimento puntuale senza base verificata."],
                reasons=["La domanda richiede un riferimento preciso che non emerge da fonti controllate."],
                risk_level="high",
            )

        if is_pdf_download_request(question) and not has_pdf:
            return GuardVerdict(
                allowed=False,
                warnings=["Download/PDF richiesto senza collegamento ufficiale verificato."],
                reasons=["Non e' presente un PDF ufficiale o un link verificato da cui scaricare il documento."],
                risk_level="high",
            )

        draft_text = _normalize_text(getattr(draft, "text", "") or "")
        if "sentenza" in draft_text and is_case_law_lookup(question) and not verified:
            return GuardVerdict(
                allowed=False,
                warnings=["La bozza cita giurisprudenza ma le fonti non sono verificate."],
                reasons=["La risposta va degradata o rigenerata con retrieval migliore."],
                risk_level="high",
            )

        return GuardVerdict(
            allowed=True,
            warnings=warnings,
            reasons=reasons,
            risk_level=risk_level,
        )


__all__ = [
    "LegalReferenceGuard",
    "build_case_law_guard_prompt",
    "build_unverified_pdf_reply",
    "collect_verified_legal_references",
    "has_verified_legal_reference",
    "has_verified_pdf_reference",
    "is_case_law_lookup",
    "is_pdf_download_request",
]
