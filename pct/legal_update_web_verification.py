from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from lxml import html as lxml_html

from lex.research.source_policy.inference import get_tier_for_domain, infer_area, normalize_domain
from lex.research.source_policy.models import Tier


STRUCTURED_ACTIONS = {"NEW_NORMATIVE", "UPDATE_NORMATIVE", "NEW_CASE_LAW", "NEW_PRASSI"}
ATTACHMENT_EXTENSIONS = (".pdf", ".xml", ".txt", ".html", ".htm", ".docx", ".doc")
ATTACHMENT_LABELS = ("allegato", "pdf", "xml", "download", "scarica", "testo", "documento")


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


def _is_allowed_attachment_url(url: str, base_url: str) -> bool:
    parsed = urlparse(str(url or ""))
    if parsed.scheme not in {"http", "https"}:
        return False
    domain = normalize_domain(parsed.netloc)
    base_domain = normalize_domain(urlparse(str(base_url or "")).netloc)
    if domain and base_domain and domain == base_domain:
        return True
    return get_tier_for_domain(domain, infer_area(base_url)).value == Tier.TIER_1.value


def _looks_like_attachment(href: str, label: str) -> bool:
    text = f"{href} {label}".lower()
    path = urlparse(href).path.lower()
    return path.endswith(ATTACHMENT_EXTENSIONS) or any(marker in text for marker in ATTACHMENT_LABELS)


def _attachment_links(html_text: str, base_url: str) -> list[dict[str, str]]:
    try:
        document = lxml_html.fromstring(html_text)
    except Exception:
        return []
    max_links = _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS", 2)
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
        links.append({"url": absolute, "label": label or "Allegato"})
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
    if "gazzetta" in text or "normativa" in text or "normative" in text or "decreto" in text or "legge" in text:
        _push("gazzetta_ufficiale")
        _push("normattiva")
    if "eur" in text or "ue" in text:
        _push("eur_lex")
    if "agenzia" in text or "entrate" in text:
        _push("agenzia_entrate")
    if "lavoro" in text:
        _push("ministero_lavoro")
    return rows[:4]


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


def _download_limited(url: str, *, timeout: int, max_bytes: int) -> tuple[bytes, str]:
    try:
        response = requests.get(
            url,
            timeout=timeout,
            stream=True,
            headers={"User-Agent": "IUSENTRA-Legal-Verification/1.0"},
        )
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
    return b"".join(chunks), str(getattr(response, "headers", {}).get("content-type", "") or "")


def _text_from_html(html_text: str) -> str:
    try:
        document = lxml_html.fromstring(html_text)
        return _clean_spaces(" ".join(document.xpath("//body//text()")) or document.text_content())
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


def _fetch_official_web_context(url: str, *, timeout: int = 8) -> str:
    target = _clean_spaces(url)
    if not target.startswith(("https://", "http://")):
        return ""
    max_bytes = _env_int("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_BYTES", 30 * 1024 * 1024)
    content, content_type = _download_limited(target, timeout=timeout, max_bytes=max_bytes)
    if not content:
        return ""
    file_type = _file_type_from_url(target, content_type)
    if file_type in {"pdf", "docx", "doc", "xml", "txt"}:
        return _truncate(_text_from_attachment(target, content, content_type), 9000)

    try:
        html_text = content.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    if not html_text.strip():
        return ""
    page_text = _text_from_html(html_text)
    sections = [page_text]
    if str(os.getenv("IUSENTRA_LEGAL_VERIFICATION_READ_ATTACHMENTS", "1")).strip().lower() not in {"0", "false", "no", "off"}:
        for link in _attachment_links(html_text, target):
            attachment_content, attachment_type = _download_limited(
                link["url"],
                timeout=timeout,
                max_bytes=max_bytes,
            )
            attachment_text = _text_from_attachment(link["url"], attachment_content, attachment_type)
            if attachment_text:
                sections.append(f"Allegato {link['label']}: {attachment_text}")
    return _truncate(" ".join(section for section in sections if section), 12000)


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


def verify_legal_update_against_public_sources(
    review: dict[str, Any],
    source: dict[str, Any],
    *,
    limit: int = 5,
) -> dict[str, Any]:
    from lex.retrieval.official_sources_retriever import search_gazzetta, search_normattiva, search_official_sources
    from lex.retrieval.official_web import search_recognized_official_web

    action = _clean_spaces(review.get("proposed_action")).upper()
    queries = _verification_queries(review)
    query = queries[0] if queries else _verification_query(review)
    confirmations: list[dict[str, Any]] = []
    warnings: list[str] = []
    searched: dict[str, Any] = {
        "query": query,
        "queries": queries,
        "source_ids": _source_ids_for_review(review, source),
        "web_context": True,
    }

    self_match = _self_confirmation(review, source)
    if self_match:
        confirmations.append(self_match)

    web_results_seen = 0
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

        try:
            web_rows = search_recognized_official_web(
                candidate_query,
                source_ids=list(searched["source_ids"] or []),
                limit_results=limit,
            )
            web_results_seen += len(web_rows)
            for row in web_rows:
                candidate = dict(row or {})
                context = _fetch_official_web_context(
                    _clean_spaces(candidate.get("url") or candidate.get("official_url") or candidate.get("url_origine"))
                )
                if context:
                    candidate["full_context"] = context
                match = _confirmation_from_row(
                    candidate,
                    origin="ricerca_web_governata",
                    review=review,
                    query=candidate_query,
                )
                if match:
                    confirmations.append(match)
        except Exception as exc:
            warnings.append(f"Ricerca web governata non completata: {_truncate(exc, 140)}")
    searched["web_results"] = web_results_seen

    confirmations = _deduplicate_confirmations(confirmations)
    official_count = sum(1 for row in confirmations if bool(row.get("official")))
    required_confirmations = 2 if action in STRUCTURED_ACTIONS else 1
    verified = official_count >= 1 and len(confirmations) >= required_confirmations
    if not verified and action in STRUCTURED_ACTIONS:
        reason = "Servono almeno una fonte primaria e una seconda conferma coerente prima della pubblicazione automatica."
    elif not verified:
        reason = "Nessuna fonte pubblica coerente trovata per la pubblicazione automatica."
    else:
        reason = "Verifica pubblica completata con fonti coerenti."

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


__all__ = ["verify_legal_update_against_public_sources"]
