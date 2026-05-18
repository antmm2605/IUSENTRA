"""Dati consultabili per le pagine di ricerca legale."""

from __future__ import annotations

import re
import os
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from pct.legal_relevance import is_low_value_public_legal_record
from pct.legal_update_batch_runner import LegalUpdateJobConfig
from pct.legal_update_autofetch import (
    LEGAL_SOURCE_QUALITY_QUESTIONS,
    LegalAutoFetchConfig,
    build_legal_update_operational_monitor,
)
from web.services.lex_studio_knowledge_status import (
    LEGAL_AGENT_FOCUS,
    build_advanced_ai_section,
    build_lex_agent_metric,
    build_lex_operational_section,
)

try:
    from lex.research.privacy_safe_query_rewriter import rewrite_query_for_legal_research as _rewrite_query_for_legal_research
    from lex.research.public_legal_research_gateway import run_public_legal_research as _run_public_legal_research
except Exception:  # pragma: no cover - la UI deve degradare senza bloccare la shell
    _rewrite_query_for_legal_research = None
    _run_public_legal_research = None

try:
    from lex.retrieval.official_sources_retriever import (
        official_archive_snapshot as _official_archive_snapshot,
        search_gazzetta as _search_gazzetta,
        search_normattiva as _search_normattiva,
    )
except Exception:  # pragma: no cover - gli archivi ufficiali sono opzionali in test/local
    _official_archive_snapshot = None
    _search_gazzetta = None
    _search_normattiva = None

try:
    from web.services.legal_official_context import build_official_context as _build_official_context
except Exception:  # pragma: no cover - la pagina resta consultabile anche senza lettura web
    _build_official_context = None


_PST_MEDIAZIONE_RECOVERY_URL = (
    "https://pst.giustizia.it/PST/page/it/"
    "ripristinati_registro_organismi_di_mediazione_elenco_enti_per_la_mediazione_"
    "e_elenco_formatori_per_la_mediazione?contentId=NWS4865&modelId=4"
)
_PST_MEDIAZIONE_RECOVERY_TITLE = (
    "Ripristinati Registro Organismi di Mediazione, Elenco Enti per la Mediazione "
    "e Elenco Formatori per la Mediazione"
)
_MEDIAZIONE_OFFICIAL_REGISTRY_RECORDS: tuple[dict[str, str], ...] = (
    {
        "id": "mediazione-registro-organismi",
        "title": "Registro Organismi di Mediazione",
        "subtitle": "Consultazione ministeriale degli organismi abilitati alla mediazione civile e commerciale.",
        "sourceHref": "https://mediazione.giustizia.it/ROM/ALBOORGANISMIMEDIAZIONE.ASPX",
        "branch": "Organismi di mediazione",
    },
    {
        "id": "mediazione-elenco-enti",
        "title": "Elenco Enti per la Mediazione",
        "subtitle": "Consultazione ministeriale degli enti accreditati per la formazione in materia di mediazione.",
        "sourceHref": "https://mediazione.giustizia.it/ROM/AlboEntiFormazione.aspx",
        "branch": "Enti per la mediazione",
    },
    {
        "id": "mediazione-elenco-formatori",
        "title": "Elenco Formatori per la Mediazione",
        "subtitle": "Consultazione ministeriale dei formatori collegati agli enti accreditati per la mediazione.",
        "sourceHref": "https://mediazione.giustizia.it/ROM/AlboFormatori.aspx",
        "branch": "Formatori per la mediazione",
    },
)
_NEWS_DATE_RE = re.compile(r"(?=\b\d{2}/\d{2}/\d{4}\b)")
_GENERIC_NEWS_CONTENT = (
    "introduce un nuovo atto o un nuovo riferimento normativo",
    "aggiorna un atto esistente e richiede controllo",
)
_GAZZETTA_LISTING_MARKERS = (
    "leggi la notizia",
    "shownewsdetail",
)
_OFFICIAL_CONTEXT_NOISE_MARKERS = (
    "home atto completo",
    "guida all'uso",
    "f.a.q",
    "inserzioni abbonamenti",
    "vendita domenica",
    "la gazzetta ufficiale guida",
)
_OFFICIAL_SOURCE_CODES = {
    "gazzetta",
    "gazzetta_ufficiale",
    "normattiva",
    "pst",
    "ministero_giustizia",
    "corte_costituzionale",
    "cassazione",
}
_LEGAL_REFERENCE_RE = re.compile(
    r"\b(?:d\.?\s*lgs\.?|d\.?\s*l\.?|d\.?\s*p\.?\s*r\.?|legge|l\.|sentenza|ordinanza|delibera|messaggio|circolare)"
    r"\b.{0,120}\b(?:n\.?\s*)?\d{1,6}(?:/\d{2,4})?\b",
    re.IGNORECASE,
)
_OFFICIAL_CONTEXT_TIMEOUT = (1.0, 2.0)
_OFFICIAL_CONTEXT_MAX_BYTES = 350_000
_OFFICIAL_CONTEXT_FETCH_LIMIT = 2


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _short(value: Any, limit: int = 220) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _flag_enabled(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "si", "sì"}


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(str(value or "").strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _restore_italian_accents(value: Any) -> str:
    text = _text(value)
    replacements = {
        "ATTIVITA'": "ATTIVITÀ",
        "AUTORITA'": "AUTORITÀ",
        "LIQUIDITA'": "LIQUIDITÀ",
        "QUALITA'": "QUALITÀ",
        "RESPONSABILITA'": "RESPONSABILITÀ",
        "SOCIETA'": "SOCIETÀ",
        "VERITA'": "VERITÀ",
        "attivita'": "attività",
        "autorita'": "autorità",
        "liquidita'": "liquidità",
        "qualita'": "qualità",
        "responsabilita'": "responsabilità",
        "societa'": "società",
        "verita'": "verità",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _readable_legal_summary(value: Any) -> str:
    text = _restore_italian_accents(value)
    text = re.sub(r"\s+Leggi la notizia\s*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s+([,)])", r"\1", text)
    text = re.sub(r"([(])\s+", r"\1", text)
    letters = [char for char in text if char.isalpha()]
    if letters and sum(1 for char in letters if char.isupper()) / max(len(letters), 1) > 0.72:
        text = text.lower()
        fixes = {
            r"\bd\.lgs\.": "D.Lgs.",
            r"\bd\.p\.r\.": "D.P.R.",
            r"\bd\.p\.c\.m\.": "D.P.C.M.",
            r"\bd\.l\.": "D.L.",
            r"\bl\.": "L.",
            r"\bue\b": "UE",
            r"\biva\b": "IVA",
            r"\bimu\b": "IMU",
        }
        for pattern, replacement in fixes.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        match = re.match(r"^(\d{2}/\d{2}/\d{4})(\s+)(.*)$", text)
        if match:
            tail = match.group(3)
            text = f"{match.group(1)}{match.group(2)}{tail[:1].upper()}{tail[1:]}"
        elif text:
            text = text[:1].upper() + text[1:]
    return text.strip(" -")


def _legal_reference_markers(*values: Any) -> list[str]:
    markers: list[str] = []
    for value in values:
        text = _text(value)
        if not text:
            continue
        for match in re.finditer(
            r"\b(?:d\.?\s*lgs\.?|d\.?\s*l\.?|d\.?\s*p\.?\s*r\.?|d\.?\s*p\.?\s*c\.?\s*m\.?|legge|l\.|sentenza|ordinanza|decreto)"
            r"\b.{0,80}\b(?:n\.?\s*)?\d{1,6}(?:/\d{2,4})?\b",
            text,
            flags=re.IGNORECASE,
        ):
            marker = _text(match.group(0)).lower()
            if marker and marker not in markers:
                markers.append(marker)
        number = _legal_reference_number(text)
        if number:
            number_marker = f"n. {number}"
            if number_marker not in markers:
                markers.append(number_marker)
    return markers


def _looks_like_cumulative_gazzetta_listing(value: Any) -> bool:
    text = _text(value)
    lower = text.lower()
    if not text:
        return False
    if sum(lower.count(marker) for marker in _GAZZETTA_LISTING_MARKERS) >= 2:
        return True
    return len(_NEWS_DATE_RE.findall(text)) >= 3 and "gazzetta" not in lower


def _extract_reference_specific_excerpt(title: Any, *values: Any, query: Any = "") -> str:
    title_text = _text(title)
    title_lower = title_text.lower()
    markers = _legal_reference_markers(title_text, query)
    for value in values:
        text = _text(value)
        if not text:
            continue
        if _looks_like_cumulative_gazzetta_listing(text):
            segments = [segment.strip(" -") for segment in _NEWS_DATE_RE.split(text) if segment.strip()]
            for segment in segments:
                lower = segment.lower()
                if (title_lower and title_lower in lower) or any(marker in lower for marker in markers):
                    cleaned = _readable_legal_summary(segment)
                    cleaned = re.sub(r"\s+Leggi la notizia\b.*$", "", cleaned, flags=re.IGNORECASE).strip(" -")
                    if cleaned:
                        return _short(cleaned, 560)
        cleaned = _readable_legal_summary(text)
        if cleaned:
            return _short(cleaned, 560)
    return _short(title_text, 560)


def _is_generic_news_content(value: Any) -> bool:
    text = _text(value).lower()
    return any(marker in text for marker in _GENERIC_NEWS_CONTENT)


def _extract_news_excerpt(row: Mapping[str, Any], *, limit: int = 360) -> str:
    title = _text(row.get("title") or row.get("headline"))
    raw_summary = _text(row.get("short_summary") or row.get("summary_short") or row.get("lead") or row.get("description"))
    content = _text(row.get("content") or row.get("body") or row.get("text"))
    candidates: list[str] = []
    if raw_summary:
        segments = [segment.strip() for segment in _NEWS_DATE_RE.split(raw_summary) if segment.strip()]
        if title:
            title_lower = title.lower()
            candidates.extend(segment for segment in segments if title_lower in segment.lower())
        candidates.extend(segments[:1] if segments else [raw_summary])
    if content and not _is_generic_news_content(content):
        candidates.append(content)
    for candidate in candidates:
        cleaned = _readable_legal_summary(candidate)
        if cleaned and title.lower() != "leggi la notizia":
            return _short(cleaned, limit)
        if cleaned and title.lower() in cleaned.lower():
            return _short(cleaned, limit)
    return _short(_readable_legal_summary(content if content and not _is_generic_news_content(content) else title), limit)


def _news_source_kind(row: Mapping[str, Any], source_href: str) -> str:
    source_code = _text(row.get("source_code")).lower()
    if bool(row.get("is_official")) or _is_official_href(source_href) or source_code in _OFFICIAL_SOURCE_CODES:
        return "fonte ufficiale"
    return "contenuto interno"


def _news_area_branch(row: Mapping[str, Any], excerpt: str) -> tuple[str, str]:
    original_area = _text(row.get("matter_name") or row.get("matter_slug"))
    original_branch = _text(row.get("submatter_name") or row.get("submatter_slug"))
    haystack = f"{row.get('title', '')} {excerpt}".lower()
    tributary_tokens = ("tribut", "iva", "imposta", "fisc", "accisa", "tassa")
    likely_default_tax = (
        "tribut" in original_area.lower()
        or original_branch.lower() == "iva"
    ) and not any(token in haystack for token in tributary_tokens)
    if "minori" in haystack or "affidamento" in haystack:
        return "Famiglia e minori", "Tutela dei minori"
    if "direttiva" in haystack and ("ue" in haystack or "unione europea" in haystack):
        if "vigilanza" in haystack or "liquidità" in haystack or "liquidita" in haystack:
            return "Unione europea", "Mercati finanziari e vigilanza"
        return "Unione europea", "Recepimento direttive"
    if likely_default_tax:
        if _text(row.get("news_type")).lower() == "normativa" or "gazzetta" in _text(row.get("source_code")).lower():
            return "Normativa", "Aggiornamento normativo"
    return original_area, original_branch


def _value(value: Any, key: str, fallback: Any = "") -> Any:
    if isinstance(value, Mapping):
        return value.get(key, fallback)
    return getattr(value, key, fallback)


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_href(value: Any, fallback: str = "") -> str:
    href = _text(value)
    if href.startswith("/") and href != "#":
        return href
    if href.startswith("https://") or href.startswith("http://"):
        return href
    return fallback


def _source_label_from_url(url: str) -> str:
    host = urlparse(url or "").netloc.lower()
    if "pst.giustizia.it" in host:
        return "Portale Servizi Telematici"
    if "giustizia.it" in host:
        return "Ministero della Giustizia"
    if "normattiva.it" in host:
        return "Normattiva"
    if "gazzettaufficiale.it" in host:
        return "Gazzetta Ufficiale"
    if "cortedicassazione.it" in host:
        return "Corte di Cassazione"
    if "cortecostituzionale.it" in host:
        return "Corte costituzionale"
    if "agenziaentrate.gov.it" in host:
        return "Agenzia delle Entrate"
    return host or "Fonte"


def _is_official_href(url: str) -> bool:
    host = urlparse(url or "").netloc.lower()
    if "@" in host:
        host = host.rsplit("@", 1)[-1]
    host = host.split(":", 1)[0].strip(".")
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in (
            "giustizia.it",
            "normattiva.it",
            "gazzettaufficiale.it",
            "cortedicassazione.it",
            "cortecostituzionale.it",
            "giustizia-amministrativa.it",
            "agenziaentrate.gov.it",
            "eur-lex.europa.eu",
        )
    )


def _metric(mid: str, label: str, value: Any, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": mid, "label": label, "value": value, "note": note, "tone": tone}


def _item(iid: str, label: str, value: Any, note: str = "", tone: str = "neutral") -> dict[str, Any]:
    return {"id": iid, "label": label, "value": value, "note": note, "tone": tone}


def _section(sid: str, title: str, kind: str, items: list[dict[str, Any]], empty: str) -> dict[str, Any]:
    return {"id": sid, "title": title, "kind": kind, "items": items, "emptyMessage": empty}


def _action(aid: str, label: str, href: str, tone: str = "neutral") -> dict[str, Any]:
    return {"id": aid, "label": label, "href": href, "method": "GET", "tone": tone}


def _warning(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _search_query(query: Mapping[str, Any] | None) -> str:
    query = query or {}
    for key in ("q", "query", "search", "cerca", "testo"):
        value = query.get(key)
        if isinstance(value, (list, tuple)):
            value = value[0] if value else ""
        text = _text(value)
        if text:
            return _short(text, 240)
    return ""


def _matches_query(record: Mapping[str, Any], search_query: str) -> bool:
    query_text = _text(search_query).lower()
    if not query_text:
        return True
    haystack = " ".join(
        _text(record.get(key)).lower()
        for key in (
            "title",
            "subtitle",
            "sourceLabel",
            "sourceKind",
            "area",
            "branch",
            "territory",
            "registryNumber",
            "registrySection",
            "taxCode",
            "vatNumber",
            "email",
            "website",
            "stateLabel",
            "sourceExcerpt",
            "date",
        )
    )
    tokens = [token for token in query_text.replace("/", " ").replace("-", " ").split() if len(token) >= 3]
    if not tokens:
        return query_text in haystack
    return all(token in haystack for token in tokens[:8]) or any(token in haystack for token in tokens[:3])


def _record_excerpt(record: Mapping[str, Any]) -> str:
    return _text(
        record.get("sourceExcerpt")
        or record.get("subtitle")
        or record.get("summary")
        or record.get("title")
    )


def _looks_like_exact_legal_reference(value: Any) -> bool:
    return bool(_LEGAL_REFERENCE_RE.search(_text(value)))


def _legal_reference_number(value: Any) -> str:
    text = _text(value)
    match = re.search(r"\bn\.?\s*(\d{1,6})(?:/\d{2,4})?\b", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _requested_reference_source(value: Any) -> str:
    text = _text(value).lower()
    if not _looks_like_exact_legal_reference(text):
        return ""
    if "corte costituzionale" in text or "cortecostituzionale.it" in text:
        return "corte_costituzionale"
    if "cassazione" in text or "corte suprema" in text or "cortedicassazione.it" in text:
        return "cassazione"
    if "consiglio di stato" in text or "giustizia-amministrativa.it" in text or re.search(r"\btar\b", text):
        return "giustizia_amministrativa"
    return ""


def _record_reference_source(record: Mapping[str, Any]) -> str:
    source_haystack = " ".join(
        _text(record.get(key))
        for key in (
            "sourceLabel",
            "sourceKind",
            "sourceHref",
            "branch",
        )
    ).lower()
    if "cortecostituzionale.it" in source_haystack or "corte costituzionale" in source_haystack:
        return "corte_costituzionale"
    if "cortedicassazione.it" in source_haystack or "cassazione" in source_haystack or "corte suprema" in source_haystack:
        return "cassazione"
    if (
        "giustizia-amministrativa.it" in source_haystack
        or "consiglio di stato" in source_haystack
        or re.search(r"\btar\b", source_haystack)
    ):
        return "giustizia_amministrativa"

    content_haystack = " ".join(
        _text(record.get(key))
        for key in (
            "title",
            "subtitle",
            "sourceExcerpt",
            "area",
        )
    ).lower()
    if "cortecostituzionale.it" in content_haystack or "corte costituzionale" in content_haystack:
        return "corte_costituzionale"
    if "cortedicassazione.it" in content_haystack or "cassazione" in content_haystack or "corte suprema" in content_haystack:
        return "cassazione"
    if (
        "giustizia-amministrativa.it" in content_haystack
        or "consiglio di stato" in content_haystack
        or re.search(r"\btar\b", content_haystack)
    ):
        return "giustizia_amministrativa"
    return ""


def _record_relevant_for_exact_reference(record: Mapping[str, Any], search_query: str) -> bool:
    reference_number = _legal_reference_number(search_query)
    if not reference_number:
        return True
    requested_source = _requested_reference_source(search_query)
    if requested_source:
        record_source = _record_reference_source(record)
        if record_source and record_source != requested_source:
            return False
    haystack = " ".join(
        _text(record.get(key))
        for key in ("title", "sourceExcerpt", "subtitle", "registryNumber", "officialContext", "contextSummary")
    ).lower()
    return bool(re.search(rf"(?<!\d){re.escape(reference_number)}(?!\d)", haystack))


def _filter_records_for_exact_reference(records: list[dict[str, Any]], search_query: str) -> list[dict[str, Any]]:
    if not _looks_like_exact_legal_reference(search_query):
        return records
    filtered = [
        record
        for record in records
        if _record_relevant_for_exact_reference(record, search_query)
    ]
    if _requested_reference_source(search_query):
        return filtered
    return filtered if filtered else records


def _record_dedupe_key(record: Mapping[str, Any]) -> str:
    record_id = _text(record.get("id"))
    if record_id.startswith("registro-mediazione-"):
        return f"mediazione:{record_id}"
    source_href = _text(record.get("sourceHref")).rstrip("/").lower()
    if source_href:
        return source_href
    return f"{_text(record.get('kind'))}:{record_id}"


def _record_richness(record: Mapping[str, Any]) -> int:
    excerpt = _record_excerpt(record)
    score = len(excerpt)
    source_kind = _text(record.get("sourceKind")).lower()
    evidence = _text(record.get("evidenceType")).lower()
    if "ufficiale" in source_kind or _is_official_href(_text(record.get("sourceHref"))):
        score += 120
    if "estratto" in evidence:
        score += 60
    if bool(record.get("contextCompleted")):
        score += 80
    if _is_generic_news_content(excerpt) or "leggi la notizia" in excerpt.lower():
        score -= 180
    return score


def _merge_richer_record(current: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    current_score = _record_richness(current)
    incoming_score = _record_richness(incoming)
    if incoming_score <= current_score:
        return current

    merged = dict(current)
    incoming_excerpt = _record_excerpt(incoming)
    current_excerpt = _record_excerpt(current)
    if incoming_excerpt and len(incoming_excerpt) > len(current_excerpt) + 30:
        merged["subtitle"] = incoming_excerpt
        merged["sourceExcerpt"] = incoming_excerpt
        if bool(incoming.get("contextCompleted")):
            merged["contextCompleted"] = True
        merged["contextSummary"] = _text(incoming.get("contextSummary")) or _short(incoming_excerpt, 520)

    incoming_href = _safe_href(incoming.get("sourceHref"))
    if incoming_href and (not _text(merged.get("sourceHref")) or _is_official_href(incoming_href)):
        merged["sourceHref"] = incoming_href

    incoming_kind = _text(incoming.get("sourceKind")).lower()
    if "ufficiale" in incoming_kind or _is_official_href(incoming_href):
        merged["sourceKind"] = "fonte ufficiale"
        merged["approvalLabel"] = _text(incoming.get("approvalLabel")) or "verificata"
        merged["approvalTone"] = _text(incoming.get("approvalTone")) or "success"
        if bool(incoming.get("contextCompleted")) or _text(incoming.get("officialContext")):
            merged["contextCompleted"] = True
    elif not _text(merged.get("sourceKind")) and _text(incoming.get("sourceKind")):
        merged["sourceKind"] = _text(incoming.get("sourceKind"))

    for key in ("sourceLabel", "evidenceType", "date", "registryNumber"):
        incoming_value = _text(incoming.get(key))
        current_value = _text(merged.get(key))
        if incoming_value and (
            not current_value
            or current_value.lower() in {"fonte interna", "contenuto interno", "riferimento fonte"}
            or key == "evidenceType" and "estratto" in incoming_value.lower()
        ):
            merged[key] = incoming_value

    for key in ("officialContext", "contextSummary", "contextStatus", "contextSource"):
        incoming_value = _text(incoming.get(key))
        if incoming_value and (not _text(merged.get(key)) or _record_richness(incoming) > current_score):
            merged[key] = incoming_value

    for key in ("keyPoints", "operationalChecks"):
        incoming_list = [item for item in _list(incoming.get(key)) if _text(item)]
        current_list = [item for item in _list(merged.get(key)) if _text(item)]
        if incoming_list and len(incoming_list) >= len(current_list):
            merged[key] = incoming_list

    for key in ("area", "branch"):
        incoming_value = _text(incoming.get(key))
        current_value = _text(merged.get(key))
        if incoming_value and (not current_value or current_value.lower() in {"informazione", "ricerca legale"}):
            merged[key] = incoming_value

    return merged


def _dedupe_records(records: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    positions: dict[str, int] = {}
    deduped: list[dict[str, Any]] = []
    for record in records:
        key = _record_dedupe_key(record)
        if key in positions:
            position = positions[key]
            deduped[position] = _merge_richer_record(deduped[position], record)
            continue
        if limit is not None and len(deduped) >= limit:
            continue
        positions[key] = len(deduped)
        deduped.append(record)
    return deduped


def _record_query_rank(record: Mapping[str, Any], search_query: str) -> tuple[int, str]:
    if not search_query:
        return (0, _text(record.get("date")))
    title = _text(record.get("title")).lower()
    excerpt = _record_excerpt(record).lower()
    query = _text(search_query).lower()
    rank = 0
    reference_number = _legal_reference_number(search_query)
    if reference_number and re.search(rf"(?<!\d){re.escape(reference_number)}(?!\d)", title):
        rank += 120
    if query and query in title:
        rank += 80
    markers = _legal_reference_markers(search_query)
    rank += sum(20 for marker in markers if marker in title)
    tokens = _context_tokens(search_query)
    rank += sum(3 for token in tokens if token in title)
    rank += sum(1 for token in tokens if token in excerpt)
    if bool(record.get("contextCompleted")):
        rank += 20
    if "ufficiale" in _text(record.get("sourceKind")).lower():
        rank += 10
    if _is_weak_source_context(record, search_query):
        rank -= 30
    return (rank, _text(record.get("date")))


def _sort_records_for_query(records: list[dict[str, Any]], search_query: str) -> list[dict[str, Any]]:
    if not search_query or not _looks_like_exact_legal_reference(search_query):
        return records
    return sorted(records, key=lambda record: _record_query_rank(record, search_query), reverse=True)


def _tone(value: Any) -> str:
    text = _text(value).lower().replace("_", " ")
    if not text:
        return "neutral"
    if text in {"published", "pubblicata", "approved", "approvata", "sincronizzata", "aggiornata", "ok"}:
        return "success"
    if text in {"pending", "pending review", "in revisione", "verifica richiesta", "da verificare"}:
        return "warning"
    if text in {"error", "errore", "fallita", "non aggiornata"}:
        return "danger"
    return "info"


def _safe_call(loader: Callable[[], Any], warnings: list[dict[str, str]], code: str, label: str) -> list[Any]:
    try:
        value = loader()
        return list(value or [])
    except Exception as exc:
        warnings.append(_warning(code, f"{label} non disponibili: {type(exc).__name__}."))
        return []


def _dashboard_snapshot(
    manager: Any,
    warnings: list[dict[str, str]],
    *,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
) -> dict[str, Any]:
    try:
        return manager.build_dashboard_snapshot(
            fascicoli=_safe_call(lambda: get_fascicoli().tutti(archiviati=True), warnings, "fascicoli_non_disponibili", "Fascicoli"),
            clienti=_safe_call(lambda: get_clienti().tutti(), warnings, "clienti_non_disponibili", "Clienti"),
            appuntamenti=_safe_call(lambda: get_agenda().tutti(), warnings, "agenda_non_disponibile", "Agenda"),
            scadenze=_safe_call(lambda: get_scadenziario().tutte(), warnings, "scadenze_non_disponibili", "Scadenze"),
            portali=[],
        )
    except Exception:
        warnings.append(_warning("snapshot_non_disponibile", "Riepilogo ricerca legale non disponibile."))
        return {}


def _pipeline_snapshot(pipeline: Any, warnings: list[dict[str, str]]) -> dict[str, Any]:
    try:
        return _dict(pipeline.dashboard_snapshot())
    except Exception:
        warnings.append(_warning("pipeline_non_disponibile", "Archivio aggiornamenti non disponibile."))
        return {}


def _news_rows(pipeline: Any, warnings: list[dict[str, str]], query: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    query = query or {}
    try:
        return list(
            pipeline.repository.list_news(
                matter_slug=_text(query.get("materia")),
                news_type=_text(query.get("tipo")),
                limit=80,
            )
        )
    except Exception as exc:
        warnings.append(_warning("news_non_disponibili", f"News giuridiche non disponibili: {type(exc).__name__}."))
        return []


def _matters(pipeline: Any, warnings: list[dict[str, str]]) -> list[dict[str, Any]]:
    try:
        return list(pipeline.repository.list_matters())
    except Exception as exc:
        warnings.append(_warning("materie_non_disponibili", f"Materie non disponibili: {type(exc).__name__}."))
        return []


def _mediazione_snapshot(manager: Any, warnings: list[dict[str, str]], query: Mapping[str, Any] | None) -> dict[str, Any]:
    query = query or {}
    try:
        snapshot = _dict(
            manager.mediazione_registry_snapshot(
                q=_text(query.get("q")),
                city=_text(query.get("city")),
                registry_number=_text(query.get("registry_number")),
                organismo_type=_text(query.get("organismo_type")),
                status=_text(query.get("status")),
                tax_code=_text(query.get("tax_code")),
                vat_number=_text(query.get("vat_number")),
                has_email=_text(query.get("has_email")),
                has_website=_text(query.get("has_website")),
            )
        )
        return snapshot
    except Exception as exc:
        warnings.append(_warning("mediazione_non_disponibile", f"Registro mediazione non disponibile: {type(exc).__name__}."))
        return {}


def _safe_news_record(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    news_id = _text(row.get("id") or row.get("slug")) or f"news_{index}"
    slug = _text(row.get("slug"))
    status = _text(row.get("publication_status") or row.get("review_status") or row.get("status"))
    source_href = _safe_href(row.get("source_url") or row.get("official_url"))
    source_label = _text(row.get("source_name") or row.get("source_code") or row.get("authority")) or _source_label_from_url(source_href) or "Fonte interna"
    source_kind = _news_source_kind(row, source_href)
    excerpt = _extract_news_excerpt(row)
    area, branch = _news_area_branch(row, excerpt)
    return {
        "id": news_id,
        "kind": "news",
        "title": _text(row.get("title") or row.get("headline")) or "News",
        "subtitle": _short(excerpt, 220),
        "sourceExcerpt": excerpt,
        "sourceLabel": source_label,
        "sourceKind": source_kind,
        "sourceHref": source_href,
        "date": _text(row.get("published_at") or row.get("created_at") or row.get("updated_at")),
        "area": area,
        "branch": branch,
        "approvalLabel": status or "pubblicata",
        "approvalTone": _tone(status or "published"),
        "legacyHref": f"/ricerca-legale/news?scheda={slug}" if slug else "/ricerca-legale/news",
        "evidenceType": "fonte ufficiale" if source_kind == "fonte ufficiale" else "fonte",
    }


def _safe_mediazione_record(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    registration = _text(row.get("registration_number") or row.get("numero_iscrizione"))
    registry_kind = _text(row.get("registry_kind") or "organismo")
    registry_section = _text(row.get("registry_section") or "Registro mediazione")
    city = _text(row.get("city") or row.get("comune"))
    province = _text(row.get("province") or row.get("provincia"))
    email = _text(row.get("email") or row.get("pec"))
    website = _text(row.get("website"))
    status = _text(row.get("status") or row.get("state") or "presente")
    tax_code = _text(row.get("tax_code"))
    vat_number = _text(row.get("vat_number"))
    source_excerpt = _short(
        " - ".join(
            part
            for part in (
                f"N. registro {registration}" if registration else "",
                registry_section,
                _text(row.get("type") or row.get("tipologia")),
                " / ".join(part for part in (city, province) if part),
                f"Stato {status}" if status else "",
                f"CF {tax_code}" if tax_code else "",
                f"P. IVA {vat_number}" if vat_number else "",
                email,
                website,
            )
            if part
        ),
        360,
    )
    return {
        "id": f"registro-mediazione-{registry_kind}-{registration or tax_code or index}",
        "kind": "mediazione",
        "title": _text(row.get("name") or row.get("denominazione")) or "Organismo di mediazione",
        "subtitle": _short(row.get("type") or row.get("tipologia") or row.get("address") or registry_section, 180),
        "sourceLabel": registry_section,
        "sourceKind": "fonte ufficiale" if row.get("official") or row.get("source") == "ministero" else "contenuto interno",
        "sourceHref": _safe_href(row.get("official_registry_url") or _MEDIAZIONE_OFFICIAL_REGISTRY_RECORDS[0]["sourceHref"]),
        "sourceExcerpt": source_excerpt,
        "date": _text(row.get("registration_date") or row.get("updated_at")),
        "area": city,
        "branch": province or registry_section,
        "territory": " - ".join(part for part in (city, province) if part),
        "stateLabel": status,
        "stateTone": _tone(status or "ok"),
        "registryNumber": registration,
        "legacyHref": f"/ricerca-legale/mediazione?organismo={registration}" if registration else "/ricerca-legale/mediazione",
        "evidenceType": "fonte",
        "taxCode": tax_code,
        "vatNumber": vat_number,
        "email": email,
        "website": website,
        "organismoType": _text(row.get("type") or row.get("tipologia")),
        "registryKind": registry_kind,
        "registrySection": registry_section,
        "statusDate": _text(row.get("status_date")),
        "isActive": bool(row.get("is_active")),
    }


def _pst_mediazione_recovery_news_record() -> dict[str, Any]:
    return {
        "id": "pst-nws4865-ripristino-mediazione",
        "kind": "news",
        "title": _PST_MEDIAZIONE_RECOVERY_TITLE,
        "subtitle": (
            "Il Portale dei Servizi Telematici comunica che dal 22/04/2026 "
            "sono stati ripristinati Registro Organismi di Mediazione, Elenco "
            "Enti per la Mediazione ed Elenco Formatori per la Mediazione."
        ),
        "sourceLabel": "Portale Servizi Telematici",
        "sourceKind": "fonte ufficiale",
        "sourceHref": _PST_MEDIAZIONE_RECOVERY_URL,
        "date": "2026-05-11",
        "area": "Mediazione",
        "branch": "Ministero della Giustizia",
        "approvalLabel": "pubblicata",
        "approvalTone": "success",
        "registryNumber": "NWS4865",
        "legacyHref": "/ricerca-legale/news?scheda=pst-nws4865-ripristino-mediazione",
        "evidenceType": "fonte ufficiale",
    }


def _mediazione_official_registry_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _MEDIAZIONE_OFFICIAL_REGISTRY_RECORDS:
        records.append(
            {
                "id": item["id"],
                "kind": "mediazione",
                "title": item["title"],
                "subtitle": item["subtitle"],
                "sourceLabel": "Ministero della Giustizia",
                "sourceKind": "fonte ufficiale",
                "sourceHref": item["sourceHref"],
                "date": "22/04/2026",
                "area": "Mediazione civile e commerciale",
                "branch": item["branch"],
                "approvalLabel": "ripristinato",
                "approvalTone": "success",
                "stateLabel": "consultabile",
                "stateTone": "success",
                "territory": "Italia",
                "registryNumber": "",
                "legacyHref": f"/ricerca-legale/mediazione?scheda={item['id']}",
                "evidenceType": "accesso ufficiale",
            }
        )
    return records


def _with_pst_recovery_news(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pst_record = _pst_mediazione_recovery_news_record()
    for record in records:
        if _text(record.get("sourceHref")) == _PST_MEDIAZIONE_RECOVERY_URL:
            return records
        if _text(record.get("id")) == pst_record["id"]:
            return records
    return [pst_record, *records]


def _search_type_label(value: Any) -> str:
    text = _text(value).lower().replace("_", " ")
    if text in {"normativa", "normative"}:
        return "normativa"
    if text in {"giurisprudenza", "jurisprudence"}:
        return "giurisprudenza"
    if text in {"prassi", "practice"}:
        return "prassi"
    if text in {"news", "notizia", "aggiornamento"}:
        return "news"
    if text in {"web ufficiale", "web_ufficiale", "official web"}:
        return "fonte ufficiale"
    return text or "fonte"


def _record_follow_up_query(record: Mapping[str, Any]) -> str:
    parts = [
        _text(record.get("title")),
        _text(record.get("area")),
        _text(record.get("branch")),
        _text(record.get("sourceLabel")),
    ]
    return _short(" ".join(part for part in parts if part), 180)


def _record_practical_use(record: Mapping[str, Any]) -> str:
    kind = _text(record.get("kind")).lower()
    title = _text(record.get("title")).lower()
    area = _text(record.get("area") or record.get("branch"))
    if "mediazione" in kind or "mediazione" in title:
        return "Usa questa scheda per verificare soggetti e requisiti collegati alla mediazione prima di scegliere organismo, ente o formatore."
    if "news" in kind:
        return "Usa l'aggiornamento per capire se il fascicolo richiede una verifica normativa, giurisprudenziale o organizzativa; apri la fonte ufficiale prima di citarlo."
    if "giurisprudenza" in kind:
        return "Usa l'estratto per individuare autorità, data e materia prima del confronto con l'archivio giurisprudenza."
    if "normativa" in kind:
        return "Usa la fonte per controllare testo vigente, data di pubblicazione e collegamenti normativi prima dell'atto o del parere."
    if "prassi" in kind:
        return "Usa il riferimento per valutare l'indirizzo amministrativo e confrontarlo con il caso concreto."
    if area:
        return f"Usa la scheda per valutare pertinenza, fonte e data rispetto all'area {area}."
    return "Usa la scheda per valutare pertinenza, fonte e data prima di inserirla nel lavoro di studio."


def _record_reliability_note(record: Mapping[str, Any]) -> str:
    source_kind = _text(record.get("sourceKind")).lower()
    source_href = _text(record.get("sourceHref"))
    if "ufficiale" in source_kind or _is_official_href(source_href):
        if bool(record.get("contextCompleted")):
            return "Contesto letto in IUSENTRA da fonte ufficiale: usa la fonte originale solo per il controllo finale prima di atti, pareri o depositi."
        return "Fonte ufficiale o istituzionale: se il contesto non è completo in pagina, apri il testo originale per il controllo finale prima di atti, pareri o depositi."
    if "verificare" in source_kind:
        return "Fonte da controllare: usa il contesto come orientamento e verifica il testo originale prima dell'uso professionale."
    if source_kind:
        return "Fonte censita nello studio: conserva il contesto utile e richiede controllo professionale prima dell'uso."
    return "Informazione disponibile nello studio: verifica la fonte prima di usarla in un atto o in un parere."


def _context_tokens(*values: Any) -> list[str]:
    stopwords = {
        "della",
        "degli",
        "delle",
        "dello",
        "alla",
        "agli",
        "alle",
        "sulla",
        "sulle",
        "decreto",
        "legislativo",
        "legge",
        "sentenza",
        "ordinanza",
        "gazzetta",
        "ufficiale",
        "normattiva",
        "marzo",
        "aprile",
        "maggio",
        "giugno",
        "luglio",
        "agosto",
        "settembre",
        "ottobre",
        "novembre",
        "dicembre",
    }
    tokens: list[str] = []
    seen: set[str] = set()
    for value in values:
        for token in re.findall(r"[^\W_]{4,}", _text(value).lower(), flags=re.UNICODE):
            if token in stopwords or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens[:12]


def _context_sentences(value: Any) -> list[str]:
    text = _restore_italian_accents(value)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    prepared = re.sub(r"\bn\.\s*", "n__DOT__ ", text, flags=re.IGNORECASE)
    prepared = re.sub(r"\bD\.\s*Lgs\.", "D Lgs", prepared, flags=re.IGNORECASE)
    prepared = re.sub(r"\bD\.\s*L\.", "D L", prepared, flags=re.IGNORECASE)
    prepared = re.sub(r"\bD\.\s*P\.\s*R\.", "D P R", prepared, flags=re.IGNORECASE)
    sentences = [
        sentence.replace("n__DOT__", "n.").strip(" -")
        for sentence in re.split(r"(?<=[.!?;:])\s+|\s{2,}", prepared)
        if 40 <= len(sentence.strip()) <= 520
    ]
    cleaned: list[str] = []
    seen: set[str] = set()
    noisy_markers = ("cookie", "privacy", "javascript", "menu", "accedi", "registrati")
    for sentence in sentences:
        lower = sentence.lower()
        if any(marker in lower for marker in noisy_markers):
            continue
        key = lower[:120]
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(sentence)
    return cleaned


def _select_context_text(official_text: Any, record: Mapping[str, Any], search_query: str, *, limit: int = 1400) -> str:
    sentences = _context_sentences(official_text)
    if not sentences:
        return _short(official_text, limit)
    tokens = _context_tokens(search_query, record.get("title"), record.get("area"), record.get("branch"))
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()
        score = sum(1 for token in tokens if token in lower)
        if any(marker in lower for marker in ("oggetto", "recepimento", "direttiva", "vigilanza", "liquidità", "liquidita", "accordi")):
            score += 2
        if score:
            scored.append((score, -index, sentence))
    selected = [row[2] for row in sorted(scored, reverse=True)[:4]] or sentences[:4]
    context = " ".join(selected)
    return _short(context, limit)


def _build_context_summary(context_text: str, record: Mapping[str, Any]) -> str:
    sentences = _context_sentences(context_text)
    if sentences:
        summary = " ".join(sentences[:2])
    else:
        summary = context_text
    if summary:
        return _short(summary, 520)
    return _short(record.get("sourceExcerpt") or record.get("subtitle") or record.get("title"), 520)


def _build_key_points(record: Mapping[str, Any], context_text: str, summary: str) -> list[str]:
    points: list[str] = []
    title = _text(record.get("title"))
    if title:
        points.append(f"Estremi: {title}")
    scope = " / ".join(part for part in (_text(record.get("area")), _text(record.get("branch"))) if part)
    if scope:
        points.append(f"Materia: {scope}")
    if summary:
        points.append(f"Oggetto: {_short(summary, 260)}")
    for sentence in _context_sentences(context_text):
        if len(points) >= 5:
            break
        cleaned = _short(sentence, 260)
        if cleaned and not any(cleaned.lower() in point.lower() or point.lower() in cleaned.lower() for point in points):
            points.append(cleaned)
    return points[:5]


def _build_operational_checks(record: Mapping[str, Any], context_text: str) -> list[str]:
    haystack = f"{record.get('title', '')} {record.get('area', '')} {record.get('branch', '')} {context_text}".lower()
    checks = [
        "Controlla decorrenza, testo vigente e norme transitorie prima di citare il riferimento.",
        "Verifica se il fascicolo richiede aggiornamento di atto, parere, scadenza o informativa al cliente.",
    ]
    if "direttiva" in haystack or "unione europea" in haystack or " ue " in f" {haystack} ":
        checks.append("Valuta il collegamento con la direttiva europea recepita e con eventuali obblighi di adeguamento.")
    if "vigilanza" in haystack or "liquidità" in haystack or "liquidita" in haystack:
        checks.append("Per pratiche societarie o finanziarie, controlla deleghe, gestione del rischio di liquidità e presidi di vigilanza.")
    if "minori" in haystack or "affidamento" in haystack:
        checks.append("Per fascicoli di famiglia, verifica impatto su affidamento, tutela del minore e provvedimenti pendenti.")
    return checks[:5]


def _clean_official_context_text(value: Any) -> str:
    text = _restore_italian_accents(value)
    if not text:
        return ""
    text = re.sub(r"^.*?\b(DECRETO LEGISLATIVO|LEGGE|DECRETO-LEGGE|DECRETO DEL PRESIDENTE|SENTENZA|ORDINANZA)\b", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\binserzioni abbonamenti vendita\b.*$", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\bHome la gazzetta ufficiale guida all'uso f\.a\.q\.\s*\}?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def _context_has_navigation_noise(value: Any) -> bool:
    lower = _text(value).lower()
    return any(marker in lower for marker in _OFFICIAL_CONTEXT_NOISE_MARKERS)


def _needs_live_official_context(record: Mapping[str, Any], search_query: str) -> bool:
    source_href = _text(record.get("sourceHref"))
    exact_reference = _looks_like_exact_legal_reference(search_query) or _looks_like_exact_legal_reference(record.get("title"))
    if exact_reference and not _record_relevant_for_exact_reference(record, search_query):
        return False
    if bool(record.get("contextCompleted")) and len(_record_excerpt(record)) >= 360:
        return False
    return bool(
        search_query
        and source_href
        and _build_official_context is not None
        and _is_official_href(source_href)
        and (
            _is_weak_source_context(record, search_query)
            or (exact_reference and not _text(record.get("officialContext")))
        )
    )


def _complete_record_context_from_official_source(
    record: Mapping[str, Any],
    search_query: str,
    *,
    context_budget: dict[str, int] | None = None,
) -> dict[str, Any]:
    enriched = dict(record)
    if context_budget is not None and context_budget.get("remaining", 0) <= 0:
        return enriched
    if not _needs_live_official_context(enriched, search_query):
        return enriched
    if context_budget is not None:
        context_budget["remaining"] = max(0, int(context_budget.get("remaining", 0)) - 1)
    try:
        payload = _build_official_context(
            _text(enriched.get("sourceHref")),
            f"{search_query} {_text(enriched.get('title'))}".strip(),
            timeout=_OFFICIAL_CONTEXT_TIMEOUT,
            max_bytes=_OFFICIAL_CONTEXT_MAX_BYTES,
            context_limit=1400,
        )
    except Exception:
        return enriched
    context_text = _clean_official_context_text(payload.get("officialContext"))
    if len(context_text) < 120:
        return enriched
    payload_summary = _text(payload.get("contextSummary"))
    summary = payload_summary if payload_summary and not _context_has_navigation_noise(payload_summary) else ""
    summary = summary or _build_context_summary(context_text, enriched)
    payload_points = [item for item in _list(payload.get("keyPoints")) if _text(item)]
    if payload_points and any(_context_has_navigation_noise(item) for item in payload_points):
        payload_points = []
    key_points = payload_points or _build_key_points(
        enriched,
        context_text,
        summary,
    )
    operational_checks = [
        item for item in _list(payload.get("operationalChecks")) if _text(item)
    ] or _build_operational_checks(enriched, context_text)
    enriched["officialContext"] = context_text
    enriched["contextSummary"] = summary
    enriched["keyPoints"] = key_points
    enriched["operationalChecks"] = operational_checks
    enriched["contextStatus"] = "contesto completo in pagina" if payload.get("contextCompleted") else "contesto ufficiale letto in anteprima"
    enriched["contextSource"] = "testo ufficiale letto da IUSENTRA"
    enriched["contextCompleted"] = bool(payload.get("contextCompleted")) or len(context_text) >= 180
    warnings = [item for item in _list(payload.get("warnings")) if _text(item)]
    if warnings:
        enriched["contextWarnings"] = warnings[:3]
    current_excerpt = _record_excerpt(enriched)
    if summary and (
        len(current_excerpt) < 260
        or _is_generic_news_content(current_excerpt)
        or _text(enriched.get("title")).lower() == current_excerpt.lower()
        or len(summary) > len(current_excerpt)
    ):
        enriched["subtitle"] = summary
        enriched["sourceExcerpt"] = summary
    return enriched


def _complete_records_context_from_official_sources(
    records: list[dict[str, Any]],
    search_query: str,
    *,
    max_reads: int = _OFFICIAL_CONTEXT_FETCH_LIMIT,
) -> tuple[list[dict[str, Any]], bool]:
    if not search_query or _build_official_context is None:
        return records, False
    completed: list[dict[str, Any]] = []
    context_budget = {"remaining": max_reads}
    attempted = False
    for record in records:
        before = context_budget["remaining"]
        completed_record = _complete_record_context_from_official_source(
            record,
            search_query,
            context_budget=context_budget,
        )
        attempted = attempted or context_budget["remaining"] < before
        completed.append(completed_record)
    return completed, attempted


def _record_context_items(record: Mapping[str, Any], excerpt: str) -> list[str]:
    items: list[str] = []
    context_summary = _text(record.get("contextSummary"))
    if context_summary:
        items.append(f"Contesto operativo: {context_summary}")
    if excerpt and not _same_context_text(context_summary, excerpt):
        items.append(f"Contenuto: {excerpt}")
    scope = " / ".join(
        part
        for part in (
            _text(record.get("area")),
            _text(record.get("branch")),
            _text(record.get("territory")),
        )
        if part
    )
    if scope:
        items.append(f"Ambito: {scope}")
    if _text(record.get("date")):
        items.append(f"Aggiornamento: {_text(record.get('date'))}")
    if _text(record.get("registryNumber")):
        items.append(f"Registro: {_text(record.get('registryNumber'))}")
    if bool(record.get("contextCompleted")):
        items.append("Lettura in pagina: contesto ricostruito dentro IUSENTRA.")
    source_label = _text(record.get("sourceLabel"))
    source_href = _text(record.get("sourceHref"))
    if source_label and ("ufficiale" in _text(record.get("sourceKind")).lower() or _is_official_href(source_href)):
        items.append(f"Fonte ufficiale: {source_label}")
        if source_href:
            if _text(record.get("officialContext")) or bool(record.get("contextCompleted")):
                items.append("Testo letto: anteprima in scheda e testo esteso disponibile nel riquadro dedicato.")
            else:
                items.append("Anteprima: testo integrale disponibile dalla fonte originale collegata.")
    elif source_label:
        items.append(f"Provenienza: {source_label}")
    return items[:6]


def _enrich_record_context(record: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    excerpt = _short(
        enriched.get("sourceExcerpt")
        or enriched.get("subtitle")
        or enriched.get("summary")
        or enriched.get("title"),
        560,
    )
    enriched["sourceExcerpt"] = excerpt
    enriched.setdefault("officialContext", "")
    enriched.setdefault("contextSummary", "")
    enriched.setdefault("keyPoints", [])
    enriched.setdefault("operationalChecks", [])
    enriched.setdefault("contextCompleted", False)
    enriched["sourceContext"] = _record_context_items(enriched, excerpt)
    enriched["practicalUse"] = _record_practical_use(enriched)
    enriched["reliabilityNote"] = _record_reliability_note(enriched)
    enriched["followUpQuery"] = _record_follow_up_query(enriched)
    return enriched


def _same_context_text(left: Any, right: Any) -> bool:
    left_text = re.sub(r"\W+", " ", _text(left).lower()).strip()
    right_text = re.sub(r"\W+", " ", _text(right).lower()).strip()
    if not left_text or not right_text:
        return False
    if left_text == right_text:
        return True
    if min(len(left_text), len(right_text)) < 80:
        return False
    return left_text.startswith(right_text) or right_text.startswith(left_text)


def _is_low_value_search_row(row: Mapping[str, Any]) -> bool:
    return is_low_value_public_legal_record(
        source_code=row.get("source_code"),
        source_name=row.get("authority") or row.get("source_name"),
        title=row.get("title") or row.get("headline") or row.get("name"),
        body_text=" ".join(
            _text(value)
            for value in (
                row.get("excerpt"),
                row.get("content"),
                row.get("summary"),
                row.get("short_summary"),
                row.get("category"),
            )
            if _text(value)
        ),
        url=row.get("official_url") or row.get("source_url") or row.get("url"),
        category=row.get("category") or row.get("type") or row.get("entity_type"),
    )


def _safe_search_record(row: Mapping[str, Any], index: int, *, search_query: str = "") -> dict[str, Any]:
    source_href = _safe_href(row.get("official_url") or row.get("source_url") or row.get("url"))
    source_label = _text(row.get("authority") or row.get("source_name") or row.get("source_code")) or _source_label_from_url(source_href)
    verified = bool(row.get("verified_reference") or row.get("is_official") or _is_official_href(source_href))
    kind = _search_type_label(row.get("type") or row.get("entity_type") or row.get("category"))
    title = _text(row.get("title") or row.get("headline") or row.get("name")) or "Fonte ricerca legale"
    raw_content = _text(row.get("content"))
    raw_excerpt = _text(row.get("excerpt") or row.get("summary") or row.get("short_summary") or raw_content)
    excerpt = _extract_reference_specific_excerpt(
        title,
        raw_excerpt,
        row.get("content"),
        row.get("summary"),
        row.get("short_summary"),
        query=search_query,
    )
    area, branch = _news_area_branch(
        {
            "matter_name": row.get("matter_name") or row.get("matter_slug") or row.get("category"),
            "submatter_name": row.get("submatter_name") or row.get("submatter_slug"),
            "news_type": row.get("type") or row.get("entity_type") or row.get("category"),
            "source_code": row.get("source_code"),
            "title": title,
        },
        excerpt,
    )
    official_context = _text(row.get("official_context") or row.get("officialContext"))
    if not official_context and verified and raw_content and len(raw_content) > max(len(excerpt), 900):
        official_context = _short(raw_content, 3600)
    context_summary = _text(row.get("context_summary") or row.get("contextSummary")) or _short(official_context or excerpt, 520)
    weak_listing = _looks_like_cumulative_gazzetta_listing(raw_excerpt)
    context_completed = bool(
        row.get("context_completed")
        or row.get("contextCompleted")
        or official_context
        or (verified and _is_official_href(source_href) and len(raw_excerpt) >= 360 and not weak_listing)
    )
    if context_completed and not official_context and verified and _is_official_href(source_href) and len(raw_excerpt) >= 360 and not weak_listing:
        official_context = _short(raw_excerpt, 2400)
    return {
        "id": _text(row.get("id")) or f"ricerca_{index}",
        "kind": kind,
        "title": title,
        "subtitle": excerpt,
        "sourceExcerpt": excerpt,
        "officialContext": official_context,
        "contextSummary": context_summary,
        "keyPoints": [item for item in _list(row.get("key_points") or row.get("keyPoints")) if _text(item)],
        "operationalChecks": [
            item for item in _list(row.get("operational_checks") or row.get("operationalChecks")) if _text(item)
        ],
        "contextCompleted": context_completed,
        "sourceLabel": source_label,
        "sourceKind": "fonte ufficiale" if verified else "fonte da verificare",
        "sourceHref": source_href,
        "date": _text(row.get("published_at") or row.get("publication_date") or row.get("date") or row.get("created_at")),
        "area": area,
        "branch": branch or kind,
        "approvalLabel": "verificata" if verified else "da verificare",
        "approvalTone": "success" if verified else "warning",
        "legacyHref": "/ricerca-legale",
        "evidenceType": "estratto fonte" if excerpt else "riferimento fonte",
    }


def _safe_public_source_record(source: Any, index: int) -> dict[str, Any]:
    source_href = _safe_href(_value(source, "url"))
    source_name = _text(_value(source, "source_name")) or _source_label_from_url(source_href)
    official = bool(_value(source, "official") or _is_official_href(source_href))
    excerpt = _short(_value(source, "excerpt"), 1400)
    kind = _search_type_label(_value(source, "source_type"))
    return {
        "id": _text(_value(source, "id")) or f"fonte_ufficiale_{index}",
        "kind": kind,
        "title": _text(_value(source, "title")) or "Fonte ufficiale",
        "subtitle": excerpt,
        "sourceExcerpt": excerpt,
        "sourceLabel": source_name,
        "sourceKind": "fonte ufficiale" if official else "fonte pubblica",
        "sourceHref": source_href,
        "date": _text(_value(source, "date")),
        "area": "Ricerca legale",
        "branch": source_name,
        "approvalLabel": "verificata" if official else "da verificare",
        "approvalTone": "success" if official else "warning",
        "legacyHref": "/ricerca-legale",
        "evidenceType": "estratto fonte" if excerpt else "riferimento fonte",
        "contextCompleted": False,
        "contextSummary": _short(excerpt, 520),
        "keyPoints": [f"Contesto ricavato: {_short(excerpt, 300)}"] if excerpt else [],
        "operationalChecks": [
            "Controlla pertinenza, decorrenza e testo ufficiale prima di usare il riferimento nel fascicolo.",
        ] if excerpt else [],
    }


def _safe_official_archive_record(row: Mapping[str, Any], index: int, *, archive: str) -> dict[str, Any]:
    source_label = _text(row.get("fonte")) or ("Normattiva" if archive == "normattiva" else "Gazzetta Ufficiale")
    title = _text(row.get("titolo")) or source_label
    excerpt = _short(row.get("testo") or row.get("excerpt") or row.get("contenuto"), 640)
    source_href = _safe_href(row.get("url_origine") or row.get("url"))
    chunk_label = _text(row.get("articolo_o_chunk") or row.get("chunk") or row.get("chunk_id"))
    return {
        "id": _text(row.get("chunk_id") or row.get("document_id") or row.get("id")) or f"{archive}_{index}",
        "kind": "normativa" if archive == "normattiva" else "news",
        "title": title,
        "subtitle": excerpt,
        "sourceExcerpt": excerpt,
        "sourceLabel": source_label,
        "sourceKind": "fonte ufficiale",
        "sourceHref": source_href,
        "date": _text(row.get("data") or row.get("published_at") or row.get("data_acquisizione")),
        "area": _text(row.get("materia")) or ("Normativa" if archive == "normattiva" else "Gazzetta Ufficiale"),
        "branch": "Archivio Normattiva" if archive == "normattiva" else "Archivio Gazzetta Ufficiale",
        "approvalLabel": "indicizzata",
        "approvalTone": "success",
        "registryNumber": chunk_label,
        "legacyHref": "/ricerca-legale",
        "evidenceType": "estratto fonte ufficiale" if excerpt else "riferimento fonte ufficiale",
        "contextCompleted": bool(excerpt),
        "contextSummary": excerpt,
        "keyPoints": [f"Estratto ufficiale: {excerpt}"] if excerpt else [],
        "operationalChecks": [
            "Verifica testo vigente, decorrenza e collegamenti prima dell'uso professionale.",
        ] if excerpt else [],
    }


def _search_repository_records(pipeline: Any, warnings: list[dict[str, str]], search_query: str) -> list[dict[str, Any]]:
    if not search_query:
        return []
    try:
        rows = list(pipeline.repository.search_lex_sources(search_query, limit=12))
    except Exception:
        warnings.append(_warning("ricerca_archivio_non_disponibile", "Archivio giuridico non disponibile per questa ricerca."))
        return []
    return [
        _safe_search_record(row, index, search_query=search_query)
        for index, row in enumerate(rows, start=1)
        if isinstance(row, Mapping) and not _is_low_value_search_row(row)
    ]


def _official_archive_records(warnings: list[dict[str, str]], search_query: str) -> list[dict[str, Any]]:
    if not search_query:
        return []
    records: list[dict[str, Any]] = []
    if _search_normattiva is not None:
        try:
            records.extend(
                _safe_official_archive_record(row, index, archive="normattiva")
                for index, row in enumerate(_search_normattiva(search_query, limit=8), start=1)
                if isinstance(row, Mapping)
            )
        except Exception:
            warnings.append(_warning("normattiva_non_disponibile", "Archivio Normattiva non disponibile per questa ricerca."))
    if _search_gazzetta is not None:
        try:
            records.extend(
                _safe_official_archive_record(row, index, archive="gazzetta")
                for index, row in enumerate(_search_gazzetta(search_query, limit=6), start=1)
                if isinstance(row, Mapping)
            )
        except Exception:
            warnings.append(_warning("gazzetta_non_disponibile", "Archivio Gazzetta Ufficiale non disponibile per questa ricerca."))
    return records


def _official_archive_counts(warnings: list[dict[str, str]]) -> dict[str, Any]:
    if _official_archive_snapshot is None:
        return {}
    try:
        return _dict(_official_archive_snapshot())
    except Exception:
        warnings.append(_warning("archivi_ufficiali_non_disponibili", "Archivi ufficiali locali non disponibili."))
        return {}


def _is_weak_source_context(record: Mapping[str, Any], search_query: str) -> bool:
    if not search_query:
        return False
    excerpt = _record_excerpt(record)
    title = _text(record.get("title"))
    lower_excerpt = excerpt.lower()
    exact_reference = _looks_like_exact_legal_reference(search_query) or _looks_like_exact_legal_reference(title)
    source_kind = _text(record.get("sourceKind")).lower()
    source_href = _text(record.get("sourceHref"))
    official = "ufficiale" in source_kind or _is_official_href(source_href)

    if "leggi la notizia" in lower_excerpt or _is_generic_news_content(excerpt):
        return True
    if exact_reference and not official:
        return True
    if exact_reference and len(excerpt) < 260:
        return True
    if exact_reference and title and excerpt.strip().lower() == title.strip().lower():
        return True
    if official and "contenuto interno" in source_kind:
        return True
    return False


def _needs_public_fallback(records: list[dict[str, Any]], search_query: str) -> bool:
    if not search_query:
        return False
    relevant_records = [
        record
        for record in records
        if not _looks_like_exact_legal_reference(search_query)
        or _record_relevant_for_exact_reference(record, search_query)
    ]
    if any(_is_weak_source_context(record, search_query) for record in relevant_records):
        return True
    exact_reference = _looks_like_exact_legal_reference(search_query)
    official_context = [
        record
        for record in relevant_records
        if "ufficiale" in _text(record.get("sourceKind")).lower()
        and len(_record_excerpt(record)) >= (180 if exact_reference else 80)
    ]
    required_sources = 1 if exact_reference else 2
    return len(official_context) < required_sources


def _public_search_records(search_query: str, warnings: list[dict[str, str]]) -> tuple[list[dict[str, Any]], bool]:
    if not search_query or _rewrite_query_for_legal_research is None or _run_public_legal_research is None:
        if search_query:
            warnings.append(_warning("ricerca_ufficiale_non_disponibile", "Ricerca su fonti ufficiali non disponibile in questo momento."))
        return [], False
    try:
        rewritten = _rewrite_query_for_legal_research(search_query)
        rewritten.can_use_ldr = False
        rewritten.local_deep_research_query = ""
        result = _run_public_legal_research(rewritten, source_mode="balanced", max_results=8)
    except Exception:
        warnings.append(_warning("ricerca_ufficiale_non_completata", "Ricerca su fonti ufficiali non completata. Riprova tra poco o apri la fonte indicata."))
        return [], True

    for message in list(getattr(result, "warnings", []) or [])[:2]:
        cleaned = _short(str(message).split(":")[0], 160)
        if cleaned:
            warnings.append(_warning("ricerca_ufficiale_avviso", cleaned))

    records = [
        _safe_public_source_record(source, index)
        for index, source in enumerate(list(getattr(result, "sources", []) or []), start=1)
    ]
    return records, True


def _filter_resolved_search_warnings(
    warnings: Iterable[Mapping[str, Any]],
    records: Iterable[Mapping[str, Any]],
) -> list[dict[str, str]]:
    has_verified_context = any(
        bool(record.get("contextCompleted"))
        and (
            "ufficiale" in _text(record.get("sourceKind")).lower()
            or _is_official_href(record.get("sourceHref"))
        )
        and (_text(record.get("officialContext")) or _text(record.get("contextSummary")))
        for record in records
    )
    if not has_verified_context:
        return [dict(warning) for warning in warnings if isinstance(warning, Mapping)]

    filtered: list[dict[str, str]] = []
    for warning in warnings:
        if not isinstance(warning, Mapping):
            continue
        code = _text(warning.get("code"))
        message = _text(warning.get("message"))
        if code == "ricerca_ufficiale_avviso" and "nessuna evidenza pubblica" in message.lower():
            continue
        filtered.append(dict(warning))
    return filtered


def _source_items(snapshot: Mapping[str, Any], update_snapshot: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in enumerate(_list(snapshot.get("source_rows")), start=1):
        if not isinstance(row, dict):
            continue
        label = _text(row.get("title") or row.get("name") or row.get("source_id") or row.get("id"))
        state = _text(row.get("freshness") or row.get("sync_status") or row.get("status"))
        items.append(_item(f"fonte_{index}", label or "Fonte", state or "censita", _text(row.get("last_checked_at") or row.get("last_synced_at")), _tone(state)))
    for index, row in enumerate(_list(update_snapshot.get("sources")), start=1):
        if not isinstance(row, dict):
            continue
        label = _text(row.get("name") or row.get("code"))
        state = "ufficiale" if row.get("is_official") else _text(row.get("trust_class") or "interna")
        items.append(_item(f"update_source_{index}", label or "Fonte aggiornamenti", state, _text(row.get("category")), "success" if row.get("is_official") else "neutral"))
    return items


def _legal_autofetch_config(config: Mapping[str, Any] | None) -> LegalAutoFetchConfig:
    cfg_source = dict(config or {})
    item_timeout_default = _positive_int(os.getenv("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"), 180)
    source_budget_default = _positive_int(os.getenv("IUSENTRA_LEGAL_AUTOFETCH_SOURCE_BUDGET"), 8)
    publish_default = _positive_int(os.getenv("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"), 80)
    job_config = LegalUpdateJobConfig(
        intelligence_db=str(
            cfg_source.get("LEGAL_INTELLIGENCE_DB")
            or os.getenv("LEGAL_INTELLIGENCE_DB")
            or os.getenv("IUSENTRA_LEGAL_INTELLIGENCE_DB")
            or "./intelligence/motori.json"
        ),
        giurisprudenza_db=str(
            cfg_source.get("GIURISPRUDENZA_DB")
            or os.getenv("GIURISPRUDENZA_DB")
            or os.getenv("IUSENTRA_GIURISPRUDENZA_DB")
            or ""
        ),
        ai_base_url=str(
            cfg_source.get("LOCAL_AI_BASE_URL")
            or cfg_source.get("PCT_LOCAL_AI_BASE_URL")
            or ""
        ).strip(),
        ai_model=str(
            cfg_source.get("LOCAL_AI_CHAT_MODEL")
            or cfg_source.get("OLLAMA_MODEL")
            or "mistral"
        ).strip(),
        export_json_enabled=_flag_enabled(cfg_source.get("LEGAL_UPDATES_EXPORT_JSON_ENABLED")),
        mirror_giurisprudenza_json_enabled=_flag_enabled(
            cfg_source.get("LEGAL_UPDATES_MIRROR_GIURISPRUDENZA_JSON_ENABLED")
        ),
    )
    return LegalAutoFetchConfig.from_job_config(
        job_config,
        source_budget=_positive_int(
            cfg_source.get("LEGAL_AUTOFETCH_SOURCE_BUDGET")
            or cfg_source.get("IUSENTRA_LEGAL_AUTOFETCH_SOURCE_BUDGET"),
            source_budget_default,
        ),
        item_timeout_seconds=_positive_int(
            cfg_source.get("LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS")
            or cfg_source.get("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS"),
            item_timeout_default,
        ),
        publish_max_items=_positive_int(
            cfg_source.get("LEGAL_UPDATES_PUBLISH_MAX_ITEMS")
            or cfg_source.get("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS"),
            publish_default,
        ),
        max_attempts=_positive_int(
            cfg_source.get("LEGAL_AUTOFETCH_MAX_ATTEMPTS")
            or os.getenv("IUSENTRA_LEGAL_AUTOFETCH_MAX_ATTEMPTS"),
            3,
        ),
        execute_due_sources=False,
    )


def _autofetch_monitor(
    pipeline: Any,
    config: Mapping[str, Any] | None,
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    cfg_source = dict(config or {})
    if not (
        cfg_source.get("LEGAL_INTELLIGENCE_DB")
        or os.getenv("LEGAL_INTELLIGENCE_DB")
        or os.getenv("IUSENTRA_LEGAL_INTELLIGENCE_DB")
    ):
        return {}
    try:
        monitor = build_legal_update_operational_monitor(
            _legal_autofetch_config(cfg_source),
            pipeline=pipeline,
        )
    except Exception:
        return {}
    return monitor if isinstance(monitor, dict) else {}


def _autofetch_tone(status: Any) -> str:
    value = _text(status).lower()
    if value == "pronta" or value == "pronto":
        return "success"
    if value in {"da_verificare", "da verificare", "non_pronta", "non pronta"}:
        return "warning"
    if value in {"errore", "failed", "timeout", "bloccata"}:
        return "danger"
    if value in {"non_monitorata", "non monitorata"}:
        return "neutral"
    return "info" if value else "neutral"


def _autofetch_source_items(monitor: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, row in enumerate(_list(monitor.get("sources")), start=1):
        if not isinstance(row, dict):
            continue
        label = _text(row.get("source_name") or row.get("source_code")) or "Fonte"
        status = _text(row.get("status") or "da_verificare")
        raw_documents = _positive_int(row.get("raw_documents"), 0)
        normalized = _positive_int(row.get("normalized_documents"), 0)
        published = _positive_int(row.get("review_published"), 0)
        pending = _positive_int(row.get("review_pending"), 0)
        count_note = (
            f"letti {raw_documents}, testo {normalized}, pubblicati {published}, da verificare {pending}"
            if raw_documents or normalized or published or pending
            else _text(row.get("reason"))
        )
        items.append(
            _item(
                f"autofetch_{index}_{_text(row.get('source_code')) or 'fonte'}",
                label,
                status.replace("_", " "),
                count_note or "Fonte censita, in attesa di acquisizione.",
                _autofetch_tone(status),
            )
        )
    return items


def _autofetch_quality_items(monitor: Mapping[str, Any]) -> list[dict[str, Any]]:
    questions = _list(monitor.get("quality_questions")) or list(LEGAL_SOURCE_QUALITY_QUESTIONS)
    return [
        _item(f"qualita_{index}", _text(question), "controllo", "Domanda obbligatoria nel ciclo DB -> fonte -> allegati -> OCR -> RAG -> Lex.", "neutral")
        for index, question in enumerate(questions[:10], start=1)
        if _text(question)
    ]


def _official_archive_items(normattiva_counts: Mapping[str, Any], gazzetta_counts: Mapping[str, Any]) -> list[dict[str, Any]]:
    normattiva_available = bool(normattiva_counts.get("available"))
    gazzetta_available = bool(gazzetta_counts.get("available"))
    return [
        _item(
            "normattiva_locale",
            "Normattiva",
            int(normattiva_counts.get("documents") or 0),
            f"{int(normattiva_counts.get('articles') or 0)} articoli indicizzati" if normattiva_available else "Archivio ufficiale non importato nel volume locale",
            "success" if normattiva_available else "warning",
        ),
        _item(
            "gazzetta_locale",
            "Gazzetta Ufficiale",
            int(gazzetta_counts.get("documents") or 0),
            f"{int(gazzetta_counts.get('chunks') or 0)} estratti indicizzati" if gazzetta_available else "Archivio ufficiale non importato nel volume locale",
            "success" if gazzetta_available else "warning",
        ),
    ]


def _mediazione_section(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    registry = _dict(snapshot.get("mediazione_registry"))
    table = _dict(registry.get("table"))
    return _section(
        "mediazione",
        "Registro mediazione",
        "fonti",
        [
            _item("totale", "Organismi", registry.get("total_rows", 0), _text(registry.get("data_origin_label") or "archivio interno"), "primary"),
            _item("filtrati", "Risultati filtrati", registry.get("filtered_rows", 0), _text(table.get("sync_status") or registry.get("data_origin")), _tone(table.get("sync_status"))),
            _item("aggiornamento", "Ultimo aggiornamento", _text(table.get("last_synced_at") or registry.get("last_successful_sync_at") or "n/d"), _text(registry.get("technical_notice")), "neutral"),
        ],
        "Registro mediazione non disponibile.",
    )


def _empty_payload(source: str, message: str, legacy_contract: str) -> dict[str, Any]:
    return {
        "source": source,
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "external_fetch": False,
            "ai_generation": False,
            "canonical_source": "backend_storico",
            "legacy_contract": legacy_contract,
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [
            _action("dashboard", "Ricerca legale", "/ricerca-legale", "primary"),
            _action("news", "News legali", "/ricerca-legale/news", "neutral"),
            _action("mediazione", "Registro mediazione", "/ricerca-legale/mediazione", "neutral"),
        ],
        "forms": [],
        "warnings": [_warning("legal_intelligence_non_disponibile", message)],
    }


def build_react_legal_intelligence_payload(
    *,
    get_legal_intelligence: Callable[[], Any],
    get_legal_update_pipeline: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_agenda: Callable[[], Any],
    get_scadenziario: Callable[[], Any],
    page: str = "dashboard",
    query: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    manager = get_legal_intelligence()
    pipeline = get_legal_update_pipeline()
    snapshot = _dashboard_snapshot(
        manager,
        warnings,
        get_fascicoli=get_fascicoli,
        get_clienti=get_clienti,
        get_agenda=get_agenda,
        get_scadenziario=get_scadenziario,
    )
    update_snapshot = _pipeline_snapshot(pipeline, warnings)
    headline = _dict(snapshot.get("headline"))
    update_headline = _dict(update_snapshot.get("headline"))
    mediazione = _mediazione_snapshot(manager, warnings, query)
    news_rows = _news_rows(pipeline, warnings, query)
    news_records = _with_pst_recovery_news(
        [_safe_news_record(row, index) for index, row in enumerate(news_rows, start=1) if isinstance(row, dict)]
    )
    mediazione_records = [
        _safe_mediazione_record(row, index)
        for index, row in enumerate(_list(mediazione.get("rows")), start=1)
        if isinstance(row, dict)
    ]
    mediazione_official_records = _mediazione_official_registry_records()
    matters = _matters(pipeline, warnings)
    source_items = _source_items(snapshot, update_snapshot)
    autofetch_monitor = _autofetch_monitor(pipeline, config, warnings)
    autofetch_source_items = _autofetch_source_items(autofetch_monitor)
    official_counts = _official_archive_counts(warnings)
    normattiva_counts = _dict(official_counts.get("normattiva"))
    gazzetta_counts = _dict(official_counts.get("gazzetta"))
    normattiva_available = bool(normattiva_counts.get("available"))
    gazzetta_available = bool(gazzetta_counts.get("available"))
    search_query = _search_query(query)
    search_records: list[dict[str, Any]] = []
    official_archive_records: list[dict[str, Any]] = []
    official_search_attempted = False
    official_context_attempted = False

    if page == "news":
        records = news_records
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence__news.json"
    elif page == "mediazione":
        records = _dedupe_records(mediazione_official_records + mediazione_records)
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence__mediazione.json"
    elif page == "ricerca-legale":
        local_matches = [
            record
            for record in news_records + mediazione_official_records + mediazione_records
            if _matches_query(record, search_query)
        ]
        search_records = _search_repository_records(pipeline, warnings, search_query)
        official_archive_records = _official_archive_records(warnings, search_query)
        combined_search = _dedupe_records(search_records + official_archive_records + local_matches)
        combined_search = _filter_records_for_exact_reference(combined_search, search_query)
        combined_search = _sort_records_for_query(combined_search, search_query)
        if _needs_public_fallback(combined_search, search_query):
            public_records, official_search_attempted = _public_search_records(search_query, warnings)
            combined_search = _dedupe_records(combined_search + public_records, limit=24)
            combined_search = _filter_records_for_exact_reference(combined_search, search_query)
            combined_search = _sort_records_for_query(combined_search, search_query)
        if search_query:
            combined_search, official_context_attempted = _complete_records_context_from_official_sources(
                combined_search,
                search_query,
            )
            combined_search = _filter_records_for_exact_reference(combined_search, search_query)
            combined_search = _sort_records_for_query(combined_search, search_query)
        records = combined_search if search_query else _dedupe_records(news_records + mediazione_official_records + mediazione_records)
        if search_query and not records:
            warnings.append(
                _warning(
                    "nessun_risultato_ricerca",
                    "Nessuna fonte trovata con questa ricerca. Prova con parole più specifiche o apri gli archivi collegati.",
                )
            )
        legacy_contract = "artifacts/react-migration/legacy-contracts/ricerca-legale.json"
    else:
        records = news_records[:8] + mediazione_official_records[:3] + mediazione_records[:5]
        legacy_contract = "artifacts/react-migration/legacy-contracts/legal-intelligence.json"

    records = [_enrich_record_context(record) for record in records]
    warnings = _filter_resolved_search_warnings(warnings, records)

    search_section = _section(
        "ricerca",
        "Ricerca fonti",
        "informazioni",
        [
            _item("query", "Termini cercati", search_query or "nessun termine", "Archivio e fonti collegate", "primary" if search_query else "neutral"),
            _item("risultati", "Risultati", len(records), "Schede disponibili", "success" if records else "neutral"),
            _item("archivio", "Archivio studio", len(search_records), "Aggiornamenti giuridici indicizzati", "info" if search_records else "neutral"),
            _item("normattiva", "Normattiva", len([record for record in official_archive_records if record.get("sourceLabel") == "Normattiva"]), "Estratti dall'archivio locale ufficiale", "success" if official_archive_records else "neutral"),
            _item("fonti_ufficiali", "Fonti ufficiali", len([record for record in records if "ufficiale" in _text(record.get("sourceKind")).lower()]), "Con estratto o riferimento consultabile", "success"),
        ],
        "Inserisci una ricerca per consultare archivio e fonti ufficiali.",
    )
    lex_presidio_section = build_lex_operational_section(config=config, focus_agent_ids=LEGAL_AGENT_FOCUS)
    advanced_ai_section = build_advanced_ai_section()
    lex_agent_metric = build_lex_agent_metric(config=config, focus_agent_ids=LEGAL_AGENT_FOCUS)

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "external_fetch": official_search_attempted or official_context_attempted,
            "ai_generation": False,
            "canonical_source": "backend_storico",
            "legacy_contract": legacy_contract,
        },
        "metrics": [
            _metric("fonti_monitorate", "Fonti monitorate", int(headline.get("fonti_monitorate") or update_headline.get("sources") or 0), "Archivio e monitor governato", "primary"),
            _metric(
                "fonti_pronte",
                "Fonti pronte",
                int(autofetch_monitor.get("sources_ready") or 0),
                "Documenti acquisiti o pubblicati",
                "success" if int(autofetch_monitor.get("sources_ready") or 0) else "neutral",
            ),
            _metric(
                "fonti_non_pronte",
                "Fonti da verificare",
                int(autofetch_monitor.get("sources_not_ready") or 0),
                "Motivo visibile nel monitor fonti",
                "warning" if int(autofetch_monitor.get("sources_not_ready") or 0) else "success",
            ),
            _metric(
                "coda_fonti",
                "Coda fonti",
                int(_dict(autofetch_monitor.get("queue")).get("queued") or 0)
                + int(_dict(autofetch_monitor.get("queue")).get("running") or 0),
                "Job in attesa o in esecuzione",
                "info",
            ),
            _metric("news_pubblicate", "News pubblicate", int(update_headline.get("published_news") or len(news_records)), "Disponibili nello studio", "info"),
            _metric("review", "In revisione", int(update_headline.get("review_pending") or headline.get("tabelle_da_validare") or 0), "Percorso governato", "warning"),
            _metric(
                "normattiva",
                "Normattiva",
                int(normattiva_counts.get("documents") or 0),
                f"{int(normattiva_counts.get('articles') or 0)} articoli, {int(normattiva_counts.get('chunks') or 0)} estratti" if normattiva_available else "Archivio ufficiale non importato nel volume locale",
                "success" if normattiva_available else "warning",
            ),
            _metric(
                "gazzetta",
                "Gazzetta",
                int(gazzetta_counts.get("documents") or 0),
                f"{int(gazzetta_counts.get('chunks') or 0)} estratti indicizzati" if gazzetta_available else "Archivio ufficiale non importato nel volume locale",
                "success" if gazzetta_available else "warning",
            ),
            _metric("mediazione", "Organismi mediazione", int(mediazione.get("total_rows") or 0), "Registro consultabile", "success" if mediazione.get("total_rows") else "neutral"),
            lex_agent_metric,
            _metric("fascicoli", "Fascicoli nel monitor", int(headline.get("fascicoli") or 0), "Informazioni studio", "neutral"),
        ],
        "sections": [
            *([search_section] if page == "ricerca-legale" else []),
            _section(
                "archivi_ufficiali",
                "Archivi ufficiali locali",
                "fonti",
                _official_archive_items(normattiva_counts, gazzetta_counts),
                "Archivi ufficiali non disponibili.",
            ),
            lex_presidio_section,
            advanced_ai_section,
            _section(
                "acquisizione_fonti",
                "Acquisizione fonti",
                "monitor",
                [
                    _item(
                        "pronte",
                        "Fonti pronte",
                        int(autofetch_monitor.get("sources_ready") or 0),
                        "Fonti con documenti letti, testo normalizzato o schede pubblicate.",
                        "success" if int(autofetch_monitor.get("sources_ready") or 0) else "neutral",
                    ),
                    _item(
                        "da_verificare",
                        "Fonti da verificare",
                        int(autofetch_monitor.get("sources_not_ready") or 0),
                        "Fonti censite ma senza documenti, con OCR/testo mancante o ultimo controllo non riuscito.",
                        "warning" if int(autofetch_monitor.get("sources_not_ready") or 0) else "success",
                    ),
                    _item(
                        "coda",
                        "Coda job",
                        int(_dict(autofetch_monitor.get("queue")).get("total") or 0),
                        "Job governati con deduplica, retry, timeout e ripresa.",
                        "info",
                    ),
                    _item(
                        "stato",
                        "Stato complessivo",
                        _dict(autofetch_monitor.get("readiness")).get("status") or "da verificare",
                        "Pronto solo quando non ci sono fonti bloccate o job falliti.",
                        _autofetch_tone(_dict(autofetch_monitor.get("readiness")).get("status")),
                    ),
                ],
                "Monitor acquisizione non disponibile.",
            ),
            _section("fonti", "Stato fonti", "fonti", autofetch_source_items or source_items, "Nessuna fonte disponibile."),
            _section("domande_qualita_fonti", "Controlli qualità fonti", "checklist", _autofetch_quality_items(autofetch_monitor), "Nessun controllo qualità disponibile."),
            _section(
                "news",
                "News legali",
                "informazioni",
                [
                    _item(record["id"], record["title"], record["date"], record["sourceLabel"], record["approvalTone"])
                    for record in news_records[:8]
                ],
                "Nessuna news pubblicata.",
            ),
            _mediazione_section({"mediazione_registry": mediazione}),
            _section(
                "materie",
                "Materie",
                "informazioni",
                [
                    _item(_text(row.get("slug") or row.get("name")), _text(row.get("name")), _text(row.get("level") or ""), _text(row.get("parent_slug")), "neutral")
                    for row in matters
                    if isinstance(row, dict)
                ],
                "Nessuna materia disponibile.",
            ),
            _section(
                "distinzione",
                "Fonte, scheda e valutazione",
                "controllo",
                [
                    _item("fonte", "Fonte", "ufficiale o interna", "Etichetta visibile su ogni riga", "success"),
                    _item("scheda", "Scheda", "data, area, stato", "Informazioni disponibili", "info"),
                    _item("revisione", "Revisione", "se presente", "Controllo umano consigliato", "warning"),
                ],
                "Nessuna distinzione disponibile.",
            ),
        ],
        "records": records,
        "actions": [
            _action("dashboard", "Ricerca legale", "/ricerca-legale", "primary"),
            _action("news", "News legali", "/ricerca-legale/news", "primary"),
            _action("mediazione", "Registro mediazione", "/ricerca-legale/mediazione", "neutral"),
            _action("giurisprudenza", "Archivio giurisprudenza", "/giurisprudenza", "neutral"),
        ],
        "forms": [],
        "warnings": warnings,
        "filters": dict(query or {}),
        "autofetchMonitor": autofetch_monitor,
    }


def build_react_legal_intelligence_error_payload(
    message: str = "Ricerca legale non disponibile.",
    *,
    legacy_contract: str = "artifacts/react-migration/legacy-contracts/legal-intelligence.json",
) -> dict[str, Any]:
    return _empty_payload("errore_controllato", message, legacy_contract)
