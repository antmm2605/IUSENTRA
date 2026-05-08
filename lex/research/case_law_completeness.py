"""Rilevamento completezza di un elemento di evidenza giurisprudenziale.

Un frammento locale è considerato incompleto se manca: URL ufficiale, testo
integrale (dispositivo o motivazione), o la corrispondenza numerica esatta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseLawCompletenessResult:
    is_case_law: bool = False
    has_number: bool = False
    has_date: bool = False
    has_court: bool = False
    has_section: bool = False
    has_official_url: bool = False
    has_full_text: bool = False
    has_pdf: bool = False
    has_dispositivo: bool = False
    has_motivazione: bool = False
    has_massima: bool = False
    is_complete: bool = False
    missing_parts: list[str] = field(default_factory=list)
    reason: str = ""


_CASE_LAW_TYPE_MARKERS = frozenset({
    "sentenza", "ordinanza", "decreto", "massima", "giurisprudenza",
    "corte di cassazione", "cassazione", "tribunale", "corte d'appello",
    "tar", "cds", "consiglio di stato", "corte costituzionale",
})

_OFFICIAL_DOMAINS = frozenset({
    "giustizia.it",
    "cortedicassazione.it",
    "cortecostituzionale.it",
    "normattiva.it",
    "giustizia-amministrativa.it",
    "italgiure.giustizia.it",
})


def _get_str(item: Any, *keys: str) -> str:
    for key in keys:
        val = getattr(item, key, None) if not isinstance(item, dict) else item.get(key)
        if val:
            return str(val).strip()
    return ""


def _has_official_url(url: str) -> bool:
    if not url:
        return False
    url_lower = url.lower()
    return any(domain in url_lower for domain in _OFFICIAL_DOMAINS)


def detect_case_law_fragment(evidence_item: Any) -> CaseLawCompletenessResult:
    """Analizza un elemento di evidenza e determina se è un frammento giurisprudenziale incompleto."""
    result = CaseLawCompletenessResult()

    title = _get_str(evidence_item, "title", "citation")
    content = _get_str(evidence_item, "content", "excerpt", "text", "summary")
    source_type = _get_str(evidence_item, "source_type", "type").lower()
    official_url = _get_str(evidence_item, "official_url", "url")

    combined = f"{title} {content} {source_type}".lower()

    # Determina se è giurisprudenza
    if any(marker in combined for marker in _CASE_LAW_TYPE_MARKERS):
        result.is_case_law = True
    elif source_type in {"sentenza", "massima", "giurisprudenza", "case_law"}:
        result.is_case_law = True

    if not result.is_case_law:
        result.reason = "Non è un elemento giurisprudenziale"
        return result

    # Controlla numero (es. "n. 7919", "12345/2025")
    import re
    if re.search(r"\bn\.\s*\d+|n°\s*\d+|\d{4,}/\d{4}", combined):
        result.has_number = True
    else:
        result.missing_parts.append("numero sentenza")

    # Controlla data
    if re.search(r"\d{1,2}/\d{1,2}/\d{4}|\d{4}[-/]\d{2}[-/]\d{2}|del\s+\d{1,2}\s+\w+\s+\d{4}", combined):
        result.has_date = True
    else:
        result.missing_parts.append("data")

    # Controlla organo giudicante
    court_patterns = [
        "cassazione", "corte d'appello", "tribunale", "tar", "cds",
        "consiglio di stato", "corte costituzionale", "sezione",
    ]
    if any(pattern in combined for pattern in court_patterns):
        result.has_court = True
    else:
        result.missing_parts.append("organo giudicante")

    # Controlla sezione
    if re.search(r"sez(?:ione)?\.?\s*[ivxlIVXL\d]+|sezione\s+\w+", combined):
        result.has_section = True

    # URL ufficiale
    result.has_official_url = _has_official_url(official_url)
    if not result.has_official_url:
        result.missing_parts.append("URL ufficiale verificato")

    # Testo integrale
    dispositivo_markers = ["dispositivo", "p.q.m.", "per questi motivi", "si rigetta", "si accoglie", "condanna"]
    motivazione_markers = ["motivazione", "ritenuto", "considerato", "in fatto", "in diritto", "svolgimento"]
    massima_markers = ["massima", "principio di diritto", "principio enunciato"]

    content_lower = content.lower()
    if any(m in content_lower for m in dispositivo_markers):
        result.has_dispositivo = True
    if any(m in content_lower for m in motivazione_markers):
        result.has_motivazione = True
    if any(m in content_lower for m in massima_markers):
        result.has_massima = True

    result.has_full_text = result.has_dispositivo or result.has_motivazione
    if not result.has_full_text:
        result.missing_parts.append("testo completo (dispositivo/motivazione)")
    if not result.has_massima:
        result.missing_parts.append("massima ufficiale")

    # PDF
    pdf_url = _get_str(evidence_item, "pdf_url", "file_url")
    result.has_pdf = bool(pdf_url and pdf_url.endswith(".pdf"))

    # Completezza: numero + data + URL ufficiale + (dispositivo o motivazione)
    result.is_complete = (
        result.has_number
        and result.has_date
        and result.has_official_url
        and result.has_full_text
    )

    if result.is_complete:
        result.reason = "Sentenza verificata con testo completo"
    elif result.missing_parts:
        result.reason = f"Frammento incompleto — mancano: {', '.join(result.missing_parts)}"
    else:
        result.reason = "Frammento incompleto"

    return result
