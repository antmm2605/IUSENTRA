from __future__ import annotations

import hashlib
import json
import os
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests
from lxml import html as lxml_html

from lex.research.source_policy.inference import get_tier_for_domain, infer_area, normalize_domain
from lex.research.source_policy.models import Tier


STRUCTURED_ACTIONS = {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}
ATTACHMENT_EXTENSIONS = (".pdf", ".xml", ".txt", ".html", ".htm", ".docx", ".doc")
ATTACHMENT_LABELS = ("allegato", "pdf", "xml", "download", "scarica", "testo", "documento")
GENERIC_ATTACHMENT_LABELS = {
    "",
    "allegato",
    "documento",
    "download",
    "leggi",
    "leggi la notizia",
    "leggi il documento",
    "scarica",
    "scarica documento",
    "scarica il documento",
    "scarica pdf",
    "scarica pdf ufficiale",
    "testo",
    "pdf",
    "read more",
    "continua",
}
OFFICIAL_ATTACHMENT_SOURCE_DOMAINS: tuple[tuple[str, str], ...] = (
    ("inps.it", "INPS"),
    ("agcom.it", "AGCOM"),
    ("anticorruzione.it", "ANAC"),
    ("inail.it", "INAIL"),
    ("lavoro.gov.it", "Ministero del Lavoro"),
    ("bancaditalia.it", "Banca d'Italia"),
    ("regione.calabria.it", "Regione Calabria"),
    ("openga.giustizia-amministrativa.it", "OpenGA Giustizia Amministrativa"),
    ("giustizia-amministrativa.it", "Giustizia Amministrativa"),
    ("gazzettaufficiale.it", "Gazzetta Ufficiale"),
    ("cortedicassazione.it", "Corte Suprema di Cassazione"),
    ("cortecostituzionale.it", "Corte costituzionale"),
    ("corteconti.it", "Corte dei Conti"),
    ("banchedati.corteconti.it", "Banca dati Corte dei Conti"),
    ("pst.giustizia.it", "Portale Servizi Telematici"),
    ("giustizia.it", "Ministero della Giustizia"),
    ("curia.europa.eu", "CURIA"),
    ("hudoc.echr.coe.int", "HUDOC"),
    ("echr.coe.int", "Corte europea dei diritti dell'uomo"),
    ("normattiva.it", "Normattiva"),
    ("eur-lex.europa.eu", "EUR-Lex"),
)
OFFICIAL_POLICY_AREAS = (
    "default",
    "normativa",
    "giurisprudenza",
    "tributario",
    "lavoro",
    "previdenza",
    "privacy",
    "societario",
    "bancario_finanziario",
    "assicurativo",
    "amministrativo",
    "appalti",
    "penale",
    "civile",
    "famiglia",
    "immigrazione",
    "fallimentare_crisi_impresa",
    "consumatori",
    "digitale_cyber",
    "ue",
    "contabile",
)


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _truncate(value: Any, limit: int = 260) -> str:
    text = _clean_spaces(value)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _env_int(name: str, default: int) -> int:
    try:
        parsed = int(str(os.getenv(name, "") or "").strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _domain(value: Any) -> str:
    return normalize_domain(urlparse(str(value or "").strip()).netloc or str(value or ""))


def _domain_matches(domain: str, allowed_domain: str) -> bool:
    normalized = normalize_domain(domain)
    allowed = normalize_domain(allowed_domain)
    return bool(normalized and allowed and (normalized == allowed or normalized.endswith("." + allowed)))


def _recognized_official_source_name(url: str) -> str:
    domain = _domain(url)
    for allowed_domain, source_name in sorted(
        OFFICIAL_ATTACHMENT_SOURCE_DOMAINS,
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if _domain_matches(domain, allowed_domain):
            return source_name
    return ""


def _is_recognized_official_url(url: str) -> bool:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    domain = normalize_domain(parsed.netloc)
    if any(_domain_matches(domain, allowed_domain) for allowed_domain, _ in OFFICIAL_ATTACHMENT_SOURCE_DOMAINS):
        return True
    return any(get_tier_for_domain(domain, area).value == Tier.TIER_1.value for area in OFFICIAL_POLICY_AREAS)


def _is_allowed_attachment_url(url: str, base_url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        return False
    domain = normalize_domain(parsed.netloc)
    base_domain = normalize_domain(urlparse(str(base_url or "")).netloc)
    if not domain or not _is_recognized_official_url(base_url):
        return False
    if any(_domain_matches(domain, allowed_domain) for allowed_domain, _ in OFFICIAL_ATTACHMENT_SOURCE_DOMAINS):
        return True
    if domain and base_domain and _domain_matches(domain, base_domain):
        return True
    return get_tier_for_domain(domain, infer_area(base_url)).value == Tier.TIER_1.value


def _looks_like_attachment(href: str, label: str) -> bool:
    text = f"{href} {label}".lower()
    path = urlparse(href).path.lower()
    query = urlparse(href).query.lower()
    real_file_extensions = tuple(ext for ext in ATTACHMENT_EXTENSIONS if ext not in {".html", ".htm"})
    if path.endswith(real_file_extensions) or path.endswith("/pdf"):
        return True
    if "downloadpdf" in path or "pdfpaginato" in path or "estensione=pdf" in query:
        return True
    if path.endswith((".html", ".htm")):
        return (
            any(marker in text for marker in ("scarica", "download", "allegato"))
            or "/allegati/" in path
            or "/download/" in path
        )
    return any(marker in text for marker in ("scarica allegato", "download allegato", "scarica documento"))


def _attachment_links(html_text: str, base_url: str) -> list[dict[str, str]]:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return []
    max_links = _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS", 4)
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in document.xpath("//a[@href]"):
        href = _clean_spaces(anchor.get("href") or "")
        label = _clean_spaces(anchor.text_content())
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            continue
        absolute = urljoin(base_url, href)
        if absolute in seen or not _looks_like_attachment(absolute, label):
            continue
        if not _is_allowed_attachment_url(absolute, base_url):
            continue
        seen.add(absolute)
        links.append({"url": absolute, "label": label or "Allegato", "attachment_type": _file_type_from_url(absolute)})
        if len(links) >= max_links:
            break
    return links


def _source_ids_for_review(review: dict[str, Any], source: dict[str, Any]) -> list[str]:
    text = " ".join(
        _clean_spaces(part).lower()
        for part in (
            review.get("classification_type"),
            review.get("proposed_action"),
            review.get("source_code"),
            review.get("source_name"),
            source.get("code"),
            source.get("category"),
            review.get("title"),
        )
    )
    rows: list[str] = []

    def _push(value: str) -> None:
        if value and value not in rows:
            rows.append(value)

    if "cassazione" in text or "giurisprudenza" in text or "case_law" in text:
        _push("cassazione")
    if any(
        marker in text
        for marker in (
            "corte dei conti",
            "corte_conti",
            "responsabilita erariale",
            "responsabilita' erariale",
            "contabile",
        )
    ):
        _push("corte_conti")
    if "gazzetta" in text or "normativa" in text or "normative" in text or "decreto" in text or "legge" in text:
        _push("gazzetta_ufficiale")
        _push("normattiva")
    if "eur" in text or "ue" in text:
        _push("eur_lex")
    if "agenzia" in text or "entrate" in text:
        _push("agenzia_entrate")
    if "anac" in text or "anticorruzione" in text or "appalti" in text:
        _push("anac")
        _push("anac_documenti")
    if "agcom" in text or "comunicazioni elettroniche" in text:
        _push("agcom")
        _push("agcom_provvedimenti")
    if "inps" in text or "previdenza" in text:
        _push("inps")
        _push("inps_circolari")
        _push("inps_messaggi")
    if "inail" in text:
        _push("inail")
    if "lavoro" in text:
        _push("ministero_lavoro")
    source_code = _clean_spaces(source.get("code") or review.get("source_code"))
    if source_code:
        _push(source_code)
    return rows[:6]


def _web_search_plans(source_ids: list[str]) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    if source_ids:
        plans.append({"scope": "mirata", "source_ids": list(source_ids)})
    plans.append({"scope": "estesa", "source_ids": []})
    return plans


def _verification_query(review: dict[str, Any]) -> str:
    parts = [
        review.get("title"),
        review.get("source_name"),
        review.get("document_date") or review.get("published_at"),
        review.get("decision_number"),
        review.get("decision_year"),
        review.get("norm_type"),
        review.get("norm_number"),
        review.get("norm_year"),
        review.get("matter_name") or review.get("matter_slug"),
    ]
    return _truncate(" ".join(_clean_spaces(part) for part in parts if _clean_spaces(part)), 420)


def _verification_queries(review: dict[str, Any]) -> list[str]:
    rows: list[str] = []

    def _push(value: Any, limit: int = 420) -> None:
        query = _truncate(value, limit)
        if query and query not in rows:
            rows.append(query)

    _push(_verification_query(review))
    title = _clean_spaces(review.get("title"))
    if title:
        _push(title)
    if review.get("norm_number") and review.get("norm_year"):
        _push(
            " ".join(
                part
                for part in (
                    review.get("norm_type"),
                    review.get("norm_number"),
                    review.get("norm_year"),
                    review.get("issuer") or review.get("source_name"),
                )
                if _clean_spaces(part)
            )
        )
    if review.get("decision_number") and review.get("decision_year"):
        _push(
            " ".join(
                part
                for part in (
                    review.get("court_name") or review.get("source_name"),
                    review.get("decision_number"),
                    review.get("decision_year"),
                    review.get("document_date") or review.get("published_at"),
                )
                if _clean_spaces(part)
            )
        )
    _push(
        " ".join(
            _clean_spaces(part)
            for part in (
                review.get("summary_short"),
                review.get("what_changes"),
                review.get("body_short"),
            )
            if _clean_spaces(part)
        ),
        520,
    )
    return rows[:5]


def _reference_tokens(review: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_number": _clean_spaces(review.get("decision_number")),
        "decision_year": _clean_spaces(review.get("decision_year")),
        "norm_number": _clean_spaces(review.get("norm_number")),
        "norm_year": _clean_spaces(review.get("norm_year")),
        "title": _clean_spaces(review.get("title")),
        "summary": _clean_spaces(review.get("summary_short") or review.get("what_changes") or review.get("body_short")),
    }


def _meaningful_tokens(value: str) -> set[str]:
    stopwords = {
        "della",
        "degli",
        "delle",
        "dello",
        "alla",
        "agli",
        "alle",
        "sulla",
        "sullo",
        "sulle",
        "ordinanza",
        "sentenza",
        "decreto",
        "legge",
        "pubblicato",
        "gazzetta",
        "ufficiale",
        "normattiva",
        "ministero",
        "corte",
        "sezione",
        "serie",
        "generale",
    }
    return {
        token
        for token in re.findall(r"[^\W_]{5,}", value.lower(), flags=re.UNICODE)
        if token not in stopwords
    }


def _title_token_overlap(expected: str, candidate: str) -> int:
    expected_tokens = _meaningful_tokens(expected)
    candidate_text = candidate.lower()
    return sum(1 for token in expected_tokens if token in candidate_text)


def _source_url_same_document(row: dict[str, Any], review: dict[str, Any]) -> bool:
    expected = _clean_spaces(review.get("source_url"))
    candidate = _clean_spaces(row.get("url") or row.get("official_url") or row.get("url_origine"))
    if not expected or not candidate:
        return False
    left = urlparse(expected)
    right = urlparse(candidate)
    return normalize_domain(left.netloc) == normalize_domain(right.netloc) and left.path.rstrip("/") == right.path.rstrip("/")


def _matched_terms(row: dict[str, Any], review: dict[str, Any]) -> list[str]:
    haystack = _row_haystack(row)
    tokens = sorted(_meaningful_tokens(_clean_spaces(review.get("title"))), key=len, reverse=True)
    return [token for token in tokens if token in haystack][:8]


def _row_haystack(row: dict[str, Any]) -> str:
    return " ".join(
        _clean_spaces(row.get(key))
        for key in (
            "title",
            "titolo",
            "excerpt",
            "testo",
            "content",
            "full_context",
            "url",
            "url_origine",
            "official_url",
            "source_name",
            "fonte",
        )
    ).lower()


def _context_excerpt(row: dict[str, Any], review: dict[str, Any], limit: int = 420) -> str:
    text = _clean_spaces(
        row.get("full_context")
        or row.get("excerpt")
        or row.get("testo")
        or row.get("content")
        or row.get("title")
        or row.get("titolo")
    )
    if len(text) <= limit:
        return text
    for token in _meaningful_tokens(_clean_spaces(review.get("title")) or _clean_spaces(review.get("summary_short"))):
        position = text.lower().find(token)
        if position >= 0:
            start = max(0, position - 140)
            return _truncate(text[start : start + limit], limit)
    return _truncate(text, limit)


def _review_source_is_official(source: dict[str, Any]) -> bool:
    return bool(source.get("is_official")) or _clean_spaces(source.get("trust_class")).upper() in {"A", "B"}


def _title_token_overlap_legacy(expected: str, candidate: str) -> int:
    expected_tokens = {
        token
        for token in re.findall(r"[^\W_]{5,}", expected.lower(), flags=re.UNICODE)
        if token not in {"della", "degli", "delle", "ordinanza", "sentenza", "decreto", "legge"}
    }
    candidate_text = candidate.lower()
    return sum(1 for token in expected_tokens if token in candidate_text)


def _matches_review_reference(row: dict[str, Any], review: dict[str, Any]) -> bool:
    ref = _reference_tokens(review)
    haystack = _row_haystack(row)
    if _source_url_same_document(row, review):
        return True
    if ref["decision_number"] and ref["decision_year"]:
        return ref["decision_number"].lower() in haystack and ref["decision_year"].lower() in haystack
    if ref["norm_number"] and ref["norm_year"]:
        return ref["norm_number"].lower() in haystack and ref["norm_year"].lower() in haystack
    if ref["title"]:
        title_overlap = _title_token_overlap(ref["title"], haystack)
        summary_overlap = _title_token_overlap(ref["summary"], haystack) if ref["summary"] else 0
        return title_overlap >= 2 or (title_overlap >= 1 and summary_overlap >= 1) or summary_overlap >= 3
    return False


def _confirmation_from_row(
    row: dict[str, Any],
    *,
    origin: str,
    review: dict[str, Any],
    query: str = "",
) -> dict[str, Any] | None:
    if not _matches_review_reference(row, review):
        return None
    url = _clean_spaces(row.get("url") or row.get("official_url") or row.get("url_origine"))
    domain = _domain(url)
    area = infer_area(_verification_query(review))
    tier = get_tier_for_domain(domain, area).value if domain else Tier.UNKNOWN.value
    source_name = _clean_spaces(row.get("source_name") or row.get("fonte") or row.get("source_id") or origin)
    return {
        "origin": origin,
        "title": _truncate(row.get("title") or row.get("titolo") or row.get("source_name") or source_name, 180),
        "source_name": source_name,
        "url": url,
        "domain": domain,
        "tier": tier,
        "official": tier == Tier.TIER_1.value or bool(row.get("official") or row.get("verified_reference")),
        "excerpt": _context_excerpt(row, review, limit=420),
        "content": _truncate(row.get("full_context") or row.get("testo") or row.get("content") or row.get("excerpt"), 12000),
        "matched_terms": _matched_terms(row, review),
        "query": _truncate(query, 220),
        "context_chars": len(_clean_spaces(row.get("full_context") or row.get("testo") or row.get("content") or row.get("excerpt"))),
    }


def _self_confirmation(review: dict[str, Any], source: dict[str, Any]) -> dict[str, Any] | None:
    url = _clean_spaces(review.get("source_url"))
    domain = _domain(url)
    if not domain:
        return None
    area = infer_area(_verification_query(review))
    tier = get_tier_for_domain(domain, area).value
    official = tier == Tier.TIER_1.value or bool(source.get("is_official"))
    if not official:
        return None
    return {
        "origin": "fonte_acquisita",
        "title": _truncate(review.get("title"), 180),
        "source_name": _clean_spaces(source.get("name") or review.get("source_name")),
        "url": url,
        "domain": domain,
        "tier": tier,
        "official": True,
        "excerpt": _truncate(review.get("summary_short") or review.get("body_short") or review.get("body_text"), 420),
        "content": _truncate(review.get("body_text") or review.get("body_short") or review.get("summary_short"), 12000),
        "matched_terms": _matched_terms({"content": review.get("body_text") or review.get("summary_short")}, review),
        "query": _truncate(_verification_query(review), 220),
        "context_chars": len(_clean_spaces(review.get("body_text") or review.get("body_short") or review.get("summary_short"))),
    }


def _deduplicate_confirmations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    positions: dict[str, int] = {}
    unique: list[dict[str, Any]] = []

    def _score(row: dict[str, Any]) -> int:
        return int(row.get("context_chars") or 0) + len(_clean_spaces(row.get("excerpt"))) + (50 if row.get("origin") == "ricerca_web_governata" else 0)

    for row in rows:
        key = _clean_spaces(row.get("url"))
        if key.lower() in {"urn:", "urn"} or len(key) < 8:
            key = f"{row.get('source_name')}|{row.get('title')}|{_clean_spaces(row.get('excerpt'))[:80]}"
        if not key:
            continue
        if key in seen:
            index = positions[key]
            if _score(row) > _score(unique[index]):
                unique[index] = row
            continue
        seen.add(key)
        positions[key] = len(unique)
        unique.append(row)
    return unique


def _file_type_from_url(url: str, content_type: str = "") -> str:
    path = urlparse(str(url or "")).path.lower()
    if path.endswith(".pdf") or "pdf" in content_type.lower():
        return "pdf"
    if path.endswith(".docx"):
        return "docx"
    if path.endswith(".doc"):
        return "doc"
    if path.endswith(".xml") or "xml" in content_type.lower():
        return "xml"
    if path.endswith((".html", ".htm")) or "html" in content_type.lower():
        return "html"
    if path.endswith(".txt") or "text/plain" in content_type.lower():
        return "txt"
    return ""


def _filename_from_url(url: str) -> str:
    path = urlparse(str(url or "")).path.rstrip("/")
    filename = path.rsplit("/", 1)[-1] if path else ""
    return _clean_spaces(filename)


def _attachment_title(label: str, attachment_url: str) -> str:
    cleaned = _clean_spaces(label)
    normalized = cleaned.lower().strip(" .:-")
    filename = _filename_from_url(attachment_url)
    if normalized in GENERIC_ATTACHMENT_LABELS or len(normalized) < 4:
        return filename or "Allegato ufficiale"
    return cleaned


def _download_cache_enabled() -> bool:
    raw = str(os.getenv("IUSENTRA_LEGAL_VERIFICATION_USE_ATTACHMENT_CACHE", "1") or "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    return bool(
        _clean_spaces(os.getenv("IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR"))
        or _clean_spaces(os.getenv("IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR"))
        or _clean_spaces(os.getenv("PCT_DATA_ROOT"))
    )


def _download_cache_roots() -> list[Path]:
    if not _download_cache_enabled():
        return []
    roots: list[Path] = []
    for name in ("IUSENTRA_LEGAL_VERIFICATION_DOWNLOAD_CACHE_DIR", "IUSENTRA_LEGAL_DOWNLOAD_CACHE_DIR"):
        configured = _clean_spaces(os.getenv(name))
        if configured:
            roots.append(Path(configured))
    data_root = _clean_spaces(os.getenv("PCT_DATA_ROOT"))
    if data_root:
        roots.append(Path(data_root) / "intelligence" / "downloads")
        roots.append(Path(data_root) / "tenants")
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _cacheable_download_type(url: str, content_type: str = "") -> str:
    file_type = _file_type_from_url(url, content_type)
    return file_type if file_type in {"pdf", "docx", "doc", "xml", "txt"} else ""


def _cache_content_type(file_type: str) -> str:
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "xml": "application/xml",
        "txt": "text/plain",
    }.get(file_type, "application/octet-stream")


def _safe_cache_filename(url: str) -> str:
    filename = _filename_from_url(url)
    if not filename:
        return ""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return safe[:180]


def _cached_download_candidates(url: str) -> list[Path]:
    filename = _safe_cache_filename(url)
    if not filename:
        return []
    domain = _domain(url) or "fonte"
    candidates: list[Path] = []
    seen: set[str] = set()
    for root in _download_cache_roots():
        direct = (
            root / filename,
            root / domain / filename,
            root / "legal_updates" / domain / filename,
            root / "cassazione" / filename,
        )
        for candidate in direct:
            key = str(candidate)
            if key not in seen:
                seen.add(key)
                candidates.append(candidate)
        if root.exists() and root.is_dir():
            try:
                for candidate in root.rglob(filename):
                    key = str(candidate)
                    if key not in seen:
                        seen.add(key)
                        candidates.append(candidate)
            except OSError:
                continue
    return candidates


def _load_cached_download(url: str, *, max_bytes: int) -> tuple[bytes, str]:
    file_type = _cacheable_download_type(url)
    if not file_type:
        return b"", ""
    for candidate in _cached_download_candidates(url):
        try:
            if not candidate.is_file() or candidate.stat().st_size > max_bytes:
                continue
            return candidate.read_bytes(), _cache_content_type(file_type)
        except OSError:
            continue
    return b"", ""


def _store_download_cache(url: str, content: bytes, content_type: str) -> None:
    if not content or not _cacheable_download_type(url, content_type):
        return
    filename = _safe_cache_filename(url)
    roots = _download_cache_roots()
    if not filename or not roots:
        return
    target_root = roots[0] / "legal_updates" / (_domain(url) or "fonte")
    try:
        target_root.mkdir(parents=True, exist_ok=True)
        target = target_root / filename
        if not target.exists() or target.stat().st_size != len(content):
            target.write_bytes(content)
    except OSError:
        return


def _download_limited(url: str, *, timeout: int, max_bytes: int, base_url: str = "") -> tuple[bytes, str]:
    target = _clean_spaces(url)
    if base_url and not _is_allowed_attachment_url(target, base_url):
        return b"", ""
    if not base_url and not _is_recognized_official_url(target):
        return b"", ""
    cached_content, cached_type = _load_cached_download(target, max_bytes=max_bytes)
    if cached_content:
        return cached_content, cached_type
    current_url = target
    redirects = 0
    try:
        while True:
            response = requests.get(
                current_url,
                timeout=timeout,
                stream=True,
                allow_redirects=False,
                headers={"User-Agent": "IUSENTRA-Legal-Verification/1.0"},
            )
            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code not in {301, 302, 303, 307, 308}:
                break
            redirects += 1
            if redirects > 3:
                return b"", str(getattr(response, "headers", {}).get("content-type", "") or "")
            location = _clean_spaces(getattr(response, "headers", {}).get("location", ""))
            next_url = urljoin(current_url, location)
            redirect_base = base_url or target
            if not _is_allowed_attachment_url(next_url, redirect_base):
                return b"", str(getattr(response, "headers", {}).get("content-type", "") or "")
            current_url = next_url
    except Exception:
        return b"", ""
    if int(getattr(response, "status_code", 0) or 0) >= 400:
        return b"", str(getattr(response, "headers", {}).get("content-type", "") or "")
    content_length = str(getattr(response, "headers", {}).get("content-length", "") or "").strip()
    if content_length.isdigit() and int(content_length) > max_bytes:
        return b"", str(getattr(response, "headers", {}).get("content-type", "") or "")
    chunks: list[bytes] = []
    total = 0
    try:
        for chunk in response.iter_content(chunk_size=65536):
            if not chunk:
                continue
            total += len(chunk)
            if total > max_bytes:
                return b"", str(getattr(response, "headers", {}).get("content-type", "") or "")
            chunks.append(chunk)
    except Exception:
        return b"", str(getattr(response, "headers", {}).get("content-type", "") or "")
    content = b"".join(chunks)
    content_type = str(getattr(response, "headers", {}).get("content-type", "") or "")
    _store_download_cache(target, content, content_type)
    return content, content_type


def _text_from_html(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
        for node in document.xpath("//script|//style|//noscript|//nav|//header|//footer"):
            try:
                node.drop_tree()
            except Exception:
                continue
        content_nodes = document.xpath("//main|//article|//*[@role='main']")
        source_node = content_nodes[0] if content_nodes else document
        return _clean_spaces(" ".join(source_node.xpath(".//text()")) or source_node.text_content())
    except Exception:
        return _clean_spaces(html_text)


def _text_from_attachment(url: str, content: bytes, content_type: str) -> str:
    file_type = _file_type_from_url(url, content_type)
    if not content:
        return ""
    if file_type in {"html", "xml", "txt"}:
        try:
            text = content.decode("utf-8", errors="ignore")
        except Exception:
            return ""
        return _text_from_html(text) if file_type == "html" else _clean_spaces(text)
    if file_type in {"pdf", "docx", "doc"}:
        try:
            from pct.document_intelligence.extraction import extract_text_from_document

            result = extract_text_from_document(content, urlparse(url).path.rsplit("/", 1)[-1] or f"allegato.{file_type}", file_type)
        except Exception:
            return ""
        if result.ok and result.text:
            return _clean_spaces(result.text)
    return ""


def _official_attachment_confirmation(
    *,
    source_url: str,
    attachment_url: str,
    label: str,
    content: bytes,
    content_type: str,
) -> dict[str, Any] | None:
    if not content:
        return None
    attachment_type = _file_type_from_url(attachment_url, content_type) or _clean_spaces(content_type).split(";", 1)[0]
    text = _clean_spaces(_text_from_attachment(attachment_url, content, content_type))
    source_name = (
        _recognized_official_source_name(source_url)
        or _recognized_official_source_name(attachment_url)
        or _domain(source_url)
    )
    if not source_name:
        return None
    unavailable_note = "Allegato scaricato dalla fonte ufficiale; testo non estraibile automaticamente."
    text_excerpt = _truncate(text or unavailable_note, 900)
    return {
        "origin": "allegato_fonte_ufficiale",
        "title": _truncate(_attachment_title(label, attachment_url), 180),
        "source_name": source_name,
        "source_url": _clean_spaces(source_url),
        "attachment_url": _clean_spaces(attachment_url),
        "attachment_type": attachment_type,
        "sha256": hashlib.sha256(content).hexdigest(),
        "text_excerpt": text_excerpt,
        "excerpt": _truncate(text or unavailable_note, 420),
        "content": _truncate(text or unavailable_note, 12000),
        "url": _clean_spaces(attachment_url),
        "domain": _domain(attachment_url),
        "tier": Tier.TIER_1.value,
        "official": True,
        "context_chars": len(text),
        "matched_terms": [],
        "query": "",
    }


def _inps_detail_json_url(url: str) -> str:
    target = _clean_spaces(url)
    parsed = urlparse(target)
    if not _domain_matches(parsed.netloc, "inps.it"):
        return ""
    if "dettaglio.circolari-e-messaggi." not in parsed.path or not parsed.path.endswith(".html"):
        return ""
    return target.replace("dettaglio.", "dettaglio.content-fragment-detail.", 1).rsplit(".html", 1)[0] + ".json"


def _decode_inps_value(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("value")
    if value is None:
        return ""
    decoded = unescape(unquote(str(value)))
    if "<" in decoded and ">" in decoded:
        return _text_from_html(decoded)
    return _clean_spaces(decoded)


def _inps_attachment_candidates(payload: dict[str, Any], source_url: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    def _push(raw: Any, label: Any = "") -> None:
        if not raw:
            return
        path = unquote(str(raw))
        absolute = urljoin("https://www.inps.it", path)
        if absolute in seen or not _is_allowed_attachment_url(absolute, source_url):
            return
        if _file_type_from_url(absolute) not in {"pdf", "docx", "doc", "xml", "txt"}:
            return
        seen.add(absolute)
        rows.append(
            {
                "url": absolute,
                "label": _decode_inps_value(label) or _filename_from_url(absolute) or "Allegato INPS",
            }
        )

    _push(payload.get("pdf"), payload.get("titolo"))
    allegati = payload.get("allegati")
    if isinstance(allegati, dict):
        for item in list(allegati.get("value") or []):
            if not isinstance(item, dict):
                continue
            _push(item.get("encodedPath") or item.get("path"), item.get("title") or item.get("name"))
    rectifications = payload.get("rectificationsObjectList")
    if isinstance(rectifications, dict):
        for item in rectifications.values():
            if not isinstance(item, dict):
                continue
            _push(item.get("encodedPath") or item.get("path"), item.get("title") or item.get("name"))
    return rows


def _fetch_inps_detail_context_with_attachments(
    url: str,
    *,
    timeout: int,
    max_bytes: int,
) -> tuple[str, list[dict[str, Any]]]:
    target = _clean_spaces(url)
    detail_url = _inps_detail_json_url(target)
    if not detail_url:
        return "", []
    content, _content_type = _download_limited(detail_url, timeout=timeout, max_bytes=max_bytes, base_url=target)
    if not content:
        return "", []
    try:
        payload = json.loads(content.decode("utf-8", errors="ignore"))
    except Exception:
        return "", []
    if not isinstance(payload, dict):
        return "", []

    sections = [
        _decode_inps_value(payload.get("titolo")),
        _decode_inps_value(payload.get("oggetto")),
        _decode_inps_value(payload.get("sommario")),
        _decode_inps_value(payload.get("testoCompleto")),
    ]
    context = _truncate(" ".join(section for section in sections if section), 12000)
    confirmations: list[dict[str, Any]] = []
    max_links = _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS", 4)
    for item in _inps_attachment_candidates(payload, target)[:max_links]:
        attachment_url = _clean_spaces(item.get("url"))
        attachment_content, attachment_type = _download_limited(
            attachment_url,
            timeout=timeout,
            max_bytes=max_bytes,
            base_url=target,
        )
        confirmation = _official_attachment_confirmation(
            source_url=target,
            attachment_url=attachment_url,
            label=_clean_spaces(item.get("label") or "Allegato INPS"),
            content=attachment_content,
            content_type=attachment_type or _clean_spaces(item.get("attachment_type")),
        )
        if confirmation:
            confirmations.append(confirmation)
    return context, confirmations


def extract_official_attachment_confirmations(
    html_text: str,
    source_url: str,
    *,
    timeout: int | None = None,
    max_bytes: int | None = None,
) -> list[dict[str, Any]]:
    """Legge solo allegati pubblici da domini istituzionali riconosciuti."""

    target = _clean_spaces(source_url)
    if not _is_recognized_official_url(target):
        return []
    resolved_timeout = int(timeout or _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_TIMEOUT_SECONDS", 8))
    resolved_max_bytes = int(
        max_bytes or _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_BYTES", 30 * 1024 * 1024)
    )
    confirmations: list[dict[str, Any]] = []
    for link in _attachment_links(html_text, target):
        attachment_url = _clean_spaces(link.get("url"))
        if not _is_allowed_attachment_url(attachment_url, target):
            continue
        content, content_type = _download_limited(
            attachment_url,
            timeout=resolved_timeout,
            max_bytes=resolved_max_bytes,
            base_url=target,
        )
        confirmation = _official_attachment_confirmation(
            source_url=target,
            attachment_url=attachment_url,
            label=_clean_spaces(link.get("label") or link.get("attachment_type") or "Allegato"),
            content=content,
            content_type=content_type or _clean_spaces(link.get("attachment_type")),
        )
        if confirmation:
            confirmations.append(confirmation)
    return confirmations


def _attachment_matches_review(confirmation: dict[str, Any], review: dict[str, Any]) -> bool:
    row = {
        "title": confirmation.get("title"),
        "content": confirmation.get("text_excerpt") or confirmation.get("excerpt"),
        "url": confirmation.get("attachment_url"),
        "source_name": confirmation.get("source_name"),
    }
    return _matches_review_reference(row, review)


def _fetch_official_web_context_with_attachments(url: str, *, timeout: int = 8) -> tuple[str, list[dict[str, Any]]]:
    target = _clean_spaces(url)
    if not target.startswith(("https://", "http://")) or not _is_recognized_official_url(target):
        return "", []
    max_bytes = _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_BYTES", 30 * 1024 * 1024)
    inps_context, inps_attachments = _fetch_inps_detail_context_with_attachments(
        target,
        timeout=timeout,
        max_bytes=max_bytes,
    )
    if inps_context or inps_attachments:
        sections = [inps_context]
        for confirmation in inps_attachments:
            excerpt = _clean_spaces(confirmation.get("text_excerpt") or confirmation.get("excerpt"))
            if excerpt:
                sections.append(f"Allegato {confirmation.get('title')}: {excerpt}")
        return _truncate(" ".join(section for section in sections if section), 12000), inps_attachments

    content, content_type = _download_limited(target, timeout=timeout, max_bytes=max_bytes)
    if not content:
        return "", []
    file_type = _file_type_from_url(target, content_type)
    if file_type in {"pdf", "docx", "doc", "xml", "txt"}:
        text = _truncate(_text_from_attachment(target, content, content_type), 9000)
        return text, []

    try:
        html_text = content.decode("utf-8", errors="ignore")
    except Exception:
        return "", []
    if not html_text.strip():
        return "", []
    page_text = _text_from_html(html_text)
    attachment_confirmations: list[dict[str, Any]] = []
    sections = [page_text]
    if str(os.getenv("IUSENTRA_LEGAL_VERIFICATION_READ_ATTACHMENTS", "1")).strip().lower() not in {"0", "false", "no", "off"}:
        attachment_confirmations = extract_official_attachment_confirmations(
            html_text,
            target,
            timeout=timeout,
            max_bytes=max_bytes,
        )
        for confirmation in attachment_confirmations:
            excerpt = _clean_spaces(confirmation.get("text_excerpt") or confirmation.get("excerpt"))
            if excerpt:
                sections.append(f"Allegato {confirmation.get('title')}: {excerpt}")
    return _truncate(" ".join(section for section in sections if section), 12000), attachment_confirmations


def _fetch_official_web_context(url: str, *, timeout: int = 8) -> str:
    context, _attachments = _fetch_official_web_context_with_attachments(url, timeout=timeout)
    return context


def _search_and_confirm(
    *,
    origin: str,
    query: str,
    review: dict[str, Any],
    fetcher,
    limit: int,
    warnings: list[str],
    fetch_web_context: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        candidates = list(fetcher(query, limit=limit) or [])
    except Exception as exc:
        warnings.append(f"{origin} non consultabile: {_truncate(exc, 140)}")
        return rows
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_row = dict(candidate)
        if fetch_web_context:
            context = _fetch_official_web_context(
                _clean_spaces(candidate_row.get("url") or candidate_row.get("official_url") or candidate_row.get("url_origine"))
            )
            if context:
                candidate_row["full_context"] = context
        match = _confirmation_from_row(candidate_row, origin=origin, review=review, query=query)
        if match:
            rows.append(match)
    return rows


def _verification_result(
    *,
    action: str,
    query: str,
    confirmations: list[dict[str, Any]],
    warnings: list[str],
    searched: dict[str, Any],
    direct_only: bool,
) -> dict[str, Any]:
    confirmations = _deduplicate_confirmations(confirmations)
    official_count = sum(1 for row in confirmations if bool(row.get("official")))
    required_confirmations = 2 if action in STRUCTURED_ACTIONS else 1
    verified = official_count >= 1 and len(confirmations) >= required_confirmations
    if verified:
        reason = "Verifica pubblica completata con fonti coerenti."
    elif direct_only and confirmations:
        reason = (
            "Fonte ufficiale diretta acquisita, ma servono ulteriori conferme "
            "prima di trattare il riferimento come completato."
        )
    elif direct_only:
        reason = "Fonte diretta non leggibile o non riconosciuta: completamento web esteso ancora da eseguire."
    elif action in STRUCTURED_ACTIONS:
        reason = "Servono almeno una fonte primaria e una seconda conferma coerente prima della pubblicazione automatica."
    else:
        reason = "Nessuna fonte pubblica coerente trovata per la pubblicazione automatica."

    return {
        "ok": verified,
        "status": "verified" if verified else "insufficient",
        "query": query,
        "required_confirmations": required_confirmations,
        "official_confirmations": official_count,
        "confirmation_count": len(confirmations),
        "confirmations": confirmations,
        "warnings": warnings,
        "searched": searched,
        "reason": reason,
    }


def verify_legal_update_against_public_sources(
    review: dict[str, Any],
    source: dict[str, Any],
    *,
    limit: int = 5,
    direct_only: bool = False,
) -> dict[str, Any]:
    action = _clean_spaces(review.get("proposed_action")).upper()
    queries = _verification_queries(review)
    query = queries[0] if queries else _verification_query(review)
    confirmations: list[dict[str, Any]] = []
    warnings: list[str] = []
    searched: dict[str, Any] = {
        "query": query,
        "queries": queries,
        "source_ids": _source_ids_for_review(review, source),
        "web_searches": [],
        "web_context": True,
        "direct_only": bool(direct_only),
    }

    self_match = _self_confirmation(review, source)
    if self_match:
        source_url = _clean_spaces(review.get("source_url"))
        try:
            direct_context, direct_attachments = _fetch_official_web_context_with_attachments(source_url)
        except Exception as exc:
            direct_context = ""
            direct_attachments = []
            warnings.append(f"Lettura diretta fonte ufficiale non completata: {_truncate(exc, 140)}")
        if direct_context:
            self_match["excerpt"] = _context_excerpt({"full_context": direct_context}, review, limit=420)
            self_match["content"] = _truncate(direct_context, 12000)
            self_match["context_chars"] = len(_clean_spaces(direct_context))
            self_match["matched_terms"] = _matched_terms(
                {
                    "title": self_match.get("title"),
                    "content": direct_context,
                    "url": source_url,
                    "source_name": self_match.get("source_name"),
                },
                review,
            )
        confirmations.append(self_match)
        for attachment_confirmation in direct_attachments:
            enriched_attachment = dict(attachment_confirmation)
            enriched_attachment["query"] = _truncate(query, 220)
            enriched_attachment["matched_terms"] = _matched_terms(
                {
                    "title": enriched_attachment.get("title"),
                    "content": enriched_attachment.get("text_excerpt"),
                    "url": enriched_attachment.get("attachment_url"),
                    "source_name": enriched_attachment.get("source_name"),
                },
                review,
            )
            confirmations.append(enriched_attachment)

    if direct_only:
        searched["web_results"] = 0
        return _verification_result(
            action=action,
            query=query,
            confirmations=confirmations,
            warnings=warnings,
            searched=searched,
            direct_only=True,
        )

    from lex.retrieval.official_sources_retriever import search_gazzetta, search_normattiva, search_official_sources
    from lex.retrieval.official_web import search_recognized_official_web

    web_results_seen = 0
    seen_web_urls: set[str] = set()
    for candidate_query in queries:
        confirmations.extend(
            _search_and_confirm(
                origin="archivio_fonti_ufficiali",
                query=candidate_query,
                review=review,
                fetcher=lambda q, limit: search_official_sources(q, limit=limit),
                limit=limit,
                warnings=warnings,
            )
        )
        confirmations.extend(
            _search_and_confirm(
                origin="archivio_normattiva",
                query=candidate_query,
                review=review,
                fetcher=lambda q, limit: search_normattiva(q, limit=limit),
                limit=limit,
                warnings=warnings,
            )
        )
        if action in {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEWS_ONLY"}:
            confirmations.extend(
                _search_and_confirm(
                    origin="archivio_gazzetta",
                    query=candidate_query,
                    review=review,
                    fetcher=lambda q, limit: search_gazzetta(q, limit=limit),
                    limit=limit,
                    warnings=warnings,
                )
            )

        for plan in _web_search_plans(list(searched["source_ids"] or [])):
            plan_source_ids = list(plan.get("source_ids") or [])
            plan_scope = _clean_spaces(plan.get("scope") or "estesa")
            try:
                web_rows = search_recognized_official_web(
                    candidate_query,
                    source_ids=plan_source_ids,
                    limit_results=max(int(limit or 0), 4),
                )
                searched["web_searches"].append(
                    {
                        "query": candidate_query,
                        "scope": plan_scope,
                        "source_ids": plan_source_ids,
                        "results": len(web_rows),
                    }
                )
                web_results_seen += len(web_rows)
                for row in web_rows:
                    candidate = dict(row or {})
                    candidate_url = _clean_spaces(candidate.get("url") or candidate.get("official_url") or candidate.get("url_origine"))
                    if candidate_url and candidate_url in seen_web_urls:
                        continue
                    if candidate_url:
                        seen_web_urls.add(candidate_url)
                    context, attachment_confirmations = _fetch_official_web_context_with_attachments(candidate_url)
                    if context:
                        candidate["full_context"] = context
                    match = _confirmation_from_row(
                        candidate,
                        origin="ricerca_web_governata",
                        review=review,
                        query=candidate_query,
                    )
                    if match:
                        match["search_scope"] = plan_scope
                        confirmations.append(match)
                    parent_page_matches = bool(match)
                    for attachment_confirmation in attachment_confirmations:
                        if parent_page_matches or _attachment_matches_review(attachment_confirmation, review):
                            enriched_attachment = dict(attachment_confirmation)
                            enriched_attachment["query"] = _truncate(candidate_query, 220)
                            enriched_attachment["search_scope"] = plan_scope
                            enriched_attachment["matched_terms"] = _matched_terms(
                                {
                                    "title": enriched_attachment.get("title"),
                                    "content": enriched_attachment.get("text_excerpt"),
                                    "url": enriched_attachment.get("attachment_url"),
                                },
                                review,
                            )
                            confirmations.append(enriched_attachment)
            except Exception as exc:
                warnings.append(f"Ricerca web governata non completata: {_truncate(exc, 140)}")
    searched["web_results"] = web_results_seen

    return _verification_result(
        action=action,
        query=query,
        confirmations=confirmations,
        warnings=warnings,
        searched=searched,
        direct_only=False,
    )


__all__ = ["extract_official_attachment_confirmations", "verify_legal_update_against_public_sources"]
