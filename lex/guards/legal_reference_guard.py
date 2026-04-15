"""Guardie di affidabilita' per riferimenti legali e download documentali di Lex."""

from __future__ import annotations

import re
from typing import Any

from lex.contracts import GuardVerdict


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
    r"\bcorte d['’]appello\b",
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


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: str) -> str:
    return _clean_spaces(value).lower()


def is_case_law_lookup(text: str) -> bool:
    haystack = _normalize_text(text)
    if not haystack:
        return False
    return any(re.search(pattern, haystack) for pattern in _CASE_LAW_PATTERNS)


def is_pdf_download_request(text: str) -> bool:
    haystack = _normalize_text(text)
    if not haystack:
        return False
    return any(re.search(pattern, haystack) for pattern in _PDF_DOWNLOAD_PATTERNS)


def has_verified_legal_reference(source: dict[str, Any]) -> bool:
    if bool(source.get("verified_reference")):
        return True
    verification_state = _normalize_text(
        source.get("stato_verifica_fonte") or source.get("stato_verifica")
    )
    ecli = _clean_spaces(source.get("ecli"))
    organo = _clean_spaces(source.get("organo_giudicante"))
    numero = _clean_spaces(source.get("numero_sentenza") or source.get("numero_provvedimento"))
    anno = _clean_spaces(source.get("anno_sentenza") or source.get("anno"))
    text = _clean_spaces(source.get("text"))
    title = _clean_spaces(source.get("title"))
    citation = _clean_spaces(source.get("citation"))
    official = _clean_spaces(
        source.get("official_url")
        or source.get("url_pagina_ufficiale")
        or source.get("url_pdf_ufficiale")
        or source.get("final_url")
        or source.get("url")
    )
    if verification_state in {"verificata", "parzialmente_verificata"} and (
        official or ecli or (organo and numero and anno)
    ):
        return True
    return bool((title or citation or text) and official)


def collect_verified_legal_references(sources: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [dict(row) for row in list(sources or []) if has_verified_legal_reference(dict(row or {}))]


def has_verified_pdf_reference(sources: list[dict[str, Any]] | None) -> bool:
    for row in collect_verified_legal_references(sources):
        final_url = _normalize_text(row.get("final_url") or row.get("url"))
        kind = _normalize_text(row.get("kind"))
        direct_pdf = _normalize_text(row.get("url_pdf_ufficiale"))
        if (
            bool(row.get("downloadable_pdf"))
            or bool(row.get("pdf_ufficiale_presente"))
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
        evidence = kwargs.get("evidence") or {}
        items = list(evidence.get("items") or [])
        if not items:
            return GuardVerdict(
                allowed=True,
                warnings=["Base legale non verificata: evita riferimenti puntuali non supportati"],
                risk_level="medium",
            )
        return GuardVerdict(allowed=True)


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
