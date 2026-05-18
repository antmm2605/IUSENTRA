from __future__ import annotations

from email.utils import parsedate_to_datetime
import hashlib
import json
import os
import re
from typing import Any, Callable
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from lxml import html as lxml_html

from pct.legal_update_source_capabilities import (
    get_source_capability,
    publication_destination_label,
    source_exclusion_reason,
)


RequestGet = Callable[..., Any]

HTML_DATE_RE = re.compile(r"\b([0-3]?\d/[01]?\d/[12]\d{3})\b")
PAGER_FRAME_RE = re.compile(r'parametriUrl\("(?P<element>[^"]+)",\s*"(?P<page>[^"]+)"\)')
ATTACHMENT_EXTENSIONS = (".pdf", ".xml", ".doc", ".docx", ".odt", ".rtf", ".txt", ".zip")
ATTACHMENT_LABELS = ("pdf", "allegato", "scarica", "download", "testo", "documento", "provvedimento")
CASSAZIONE_LATEST_SOURCE_CODE = "cassazione_ultime_sent_ord_questioni"
CASSAZIONE_LATEST_CATEGORY_MARKERS = (
    "giurisprudenza_penale.page",
    "giurisprudenza_civile.page",
)
CASSAZIONE_DETAIL_URL_MARKERS = (
    "/it/civile_dettaglio.page",
    "/it/penale_dettaglio.page",
    "/it/qsp_dettaglio.page",
    "/it/qsc_dettaglio.page",
    "/it/quc_dettaglio.page",
    "/it/rlc_dettaglio.page",
    "/it/rlp_dettaglio.page",
    "/it/su_dettaglio.page",
)


def fetch_source_documents(source: dict[str, Any], *, request_get: RequestGet) -> list[dict[str, Any]]:
    response = _request(source["base_url"], request_get=request_get)
    content_type = _header(response, "content-type")
    text = _response_text(response)
    parser_type = _clean_spaces(source.get("parser_type")).lower()
    capability = get_source_capability(source.get("code"), category=source.get("category"))

    if parser_type == "ckan_json" or capability.item_strategy == "ckan_package_resources":
        docs = _extract_ckan_items(source, source["base_url"], text, request_get=request_get)
    elif parser_type in {"feed", "rss", "atom"} or _looks_like_feed(text, content_type):
        docs = _extract_feed_items(source, source["base_url"], text, request_get=request_get)
    elif _clean_spaces(source.get("code")).lower() == CASSAZIONE_LATEST_SOURCE_CODE:
        docs = _extract_cassazione_latest(source, text, request_get=request_get)
    else:
        docs = _extract_html_listing(source, source["base_url"], text)
        docs = _fetch_detail_pages(source, docs, request_get=request_get)
        for page in _extract_pager_frames(text):
            page_url = _set_query_param(source["base_url"], "frame3_item", page)
            try:
                page_response = _request(page_url, request_get=request_get)
            except Exception:
                continue
            page_docs = _extract_html_listing(source, page_url, _response_text(page_response))
            docs.extend(_fetch_detail_pages(source, page_docs, request_get=request_get))
        docs = _merge_unique_documents(docs)

    if not docs:
        docs = [_fallback_document(source, text)]
    http_status = int(getattr(response, "status_code", 200) or 0)
    for row in docs:
        _apply_capability_metadata(source, row)
        row.setdefault("raw_html", text[:20000])
        row.setdefault("raw_text", row.get("body_short") or "")
        row["content_hash"] = _sha256(json.dumps(row, ensure_ascii=False, sort_keys=True))
        row["http_status"] = http_status
        row["fetch_status"] = "fetched" if http_status < 400 else "error"
    return docs


def _request(url: str, *, request_get: RequestGet):
    return request_get(
        url,
        timeout=25,
        headers={"User-Agent": "IUSENTRA-Legal-Updates/1.0"},
    )


def _header(response: Any, name: str) -> str:
    headers = getattr(response, "headers", {}) or {}
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return str(value or "")
    return ""


def _response_text(response: Any) -> str:
    if hasattr(response, "text"):
        return str(response.text or "")
    if hasattr(response, "content"):
        return bytes(response.content or b"").decode("utf-8", errors="ignore")
    return ""


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _env_int(name: str, default: int) -> int:
    try:
        parsed = int(str(os.getenv(name, "") or "").strip())
        return parsed if parsed > 0 else default
    except (TypeError, ValueError):
        return default


def _truncate(value: Any, limit: int = 240) -> str:
    cleaned = _clean_spaces(value)
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 3].rstrip() + "..."


def _sha256(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def _normalize_document_url(url: str) -> str:
    split = urlsplit(str(url or ""))
    return urlunsplit((split.scheme, split.netloc, split.path, split.query, ""))


def _parse_pub_date(value: Any) -> str:
    text = _clean_spaces(value)
    if not text:
        return ""
    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        pass
    match = HTML_DATE_RE.search(text)
    if not match:
        return ""
    day, month, year = match.group(1).split("/")
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _looks_like_feed(content: str, content_type: str) -> bool:
    head = content.lstrip()[:400].lower()
    return (
        "xml" in (content_type or "").lower()
        or head.startswith("<rss")
        or head.startswith("<feed")
        or (head.startswith("<?xml") and ("<rss" in head or "<feed" in head))
    )


def _extract_feed_items(source: dict[str, Any], base_url: str, content: str, *, request_get: RequestGet) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    docs: list[dict[str, Any]] = []
    for item in root.findall(".//item") + root.findall(".//{*}entry"):
        title = _clean_spaces(item.findtext("title") or item.findtext("{*}title"))
        link = _clean_spaces(item.findtext("link") or item.findtext("{*}link"))
        if not link:
            link_node = item.find("{*}link")
            if link_node is not None:
                link = _clean_spaces(link_node.attrib.get("href") or link_node.text)
        summary = _clean_spaces(
            item.findtext("description")
            or item.findtext("{*}summary")
            or item.findtext("{*}content")
        )
        published_at = _parse_pub_date(
            item.findtext("pubDate") or item.findtext("{*}published") or item.findtext("{*}updated")
        )
        if not title and not link:
            continue
        absolute_url = _normalize_document_url(urljoin(base_url, link or source.get("base_url") or ""))
        row = {
            "external_id": _sha256(f"{source.get('code')}|{absolute_url}|{title}"),
            "source_url": absolute_url,
            "title": title or absolute_url,
            "published_at": published_at,
            "raw_html": "",
            "raw_text": summary,
            "body_short": _truncate(summary or title),
        }
        if _should_fetch_detail(source, row) or len(summary) < 160:
            _merge_detail(source, row, absolute_url, request_get=request_get)
        docs.append(row)
    return _merge_unique_documents(docs)


def _extract_html_listing(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError):
        return []
    docs: list[dict[str, Any]] = []
    for node in tree.xpath("//article|//li|//div[contains(@class,'card')]|//div[contains(@class,'item')]"):
        anchors = node.xpath(".//a[@href]")
        if not anchors:
            continue
        title = ""
        href = ""
        for anchor in anchors:
            candidate_title = _clean_spaces(anchor.text_content())
            candidate_href = _clean_spaces(anchor.attrib.get("href"))
            if not candidate_href or candidate_href.startswith("#") or candidate_href.lower().startswith(("javascript:", "mailto:")):
                continue
            if len(candidate_title) >= 8:
                title = candidate_title
                href = candidate_href
                break
        if not href:
            continue
        absolute_url = _normalize_document_url(urljoin(base_url, href))
        row_text = _clean_spaces(" ".join(node.xpath(".//text()"))) or title
        if source_exclusion_reason(source, title=title, body_text=row_text, url=absolute_url):
            continue
        published_at = _parse_pub_date(f"{title} {row_text}")
        docs.append(
            {
                "external_id": _sha256(f"{source.get('code')}|{absolute_url}|{published_at or title.lower()}"),
                "source_url": absolute_url,
                "title": title,
                "published_at": published_at,
                "raw_html": "",
                "raw_text": row_text,
                "body_short": _truncate(row_text or title),
                "attachments_json": _attachment_candidates(row_text, base_url),
            }
        )
    if docs:
        return _merge_unique_documents(docs)
    for anchor in tree.xpath("//a[@href]"):
        title = _clean_spaces(anchor.text_content())
        href = _clean_spaces(anchor.attrib.get("href"))
        if not href or len(title) < 12 or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            continue
        absolute_url = _normalize_document_url(urljoin(base_url, href))
        row_text = _clean_spaces(" ".join(anchor.xpath("./ancestor::*[self::li or self::article or self::div][1]//text()"))) or title
        if source_exclusion_reason(source, title=title, body_text=row_text, url=absolute_url):
            continue
        docs.append(
            {
                "external_id": _sha256(f"{source.get('code')}|{absolute_url}|{title.lower()}"),
                "source_url": absolute_url,
                "title": title,
                "published_at": _parse_pub_date(f"{title} {row_text}"),
                "raw_html": "",
                "raw_text": row_text,
                "body_short": _truncate(row_text or title),
            }
        )
    if docs:
        return _merge_unique_documents(docs)
    plain = _text_from_html_content(content)
    if source_exclusion_reason(source, title=_clean_spaces(tree.findtext(".//title")), body_text=plain, url=base_url):
        return []
    return [
        {
            "external_id": _sha256(f"{source.get('code')}|{base_url}|fallback"),
            "source_url": base_url,
            "title": _clean_spaces(tree.findtext(".//title")) or source.get("name") or base_url,
            "published_at": "",
            "raw_html": content[:20000],
            "raw_text": plain,
            "body_short": _truncate(plain),
            "attachments_json": _attachment_links(content, base_url),
        }
    ]


def _fetch_detail_pages(source: dict[str, Any], docs: list[dict[str, Any]], *, request_get: RequestGet) -> list[dict[str, Any]]:
    detail_limit = _env_int("IUSENTRA_LEGAL_DETAIL_MAX_ITEMS", 30)
    fetched = 0
    for row in docs:
        if fetched >= detail_limit:
            break
        if not _should_fetch_detail(source, row):
            continue
        if _merge_detail(source, row, _clean_spaces(row.get("source_url")), request_get=request_get):
            fetched += 1
    return _merge_unique_documents(docs)


def _should_fetch_detail(source: dict[str, Any], row: dict[str, Any]) -> bool:
    capability = get_source_capability(source.get("code"), category=source.get("category"))
    strategy = capability.detail_strategy
    if strategy in {"metadata_only", "download_metadata", "manual_free_web_only"}:
        return False
    url = _clean_spaces(row.get("source_url"))
    if not url or url == _clean_spaces(source.get("base_url")):
        return False
    if strategy in {"detail_html", "detail_if_useful", "feed_detail_if_poor", "detail_html_backfill_only", "resource_detail_if_document"}:
        return True
    return False


def _merge_detail(source: dict[str, Any], row: dict[str, Any], url: str, *, request_get: RequestGet) -> bool:
    if not url:
        return False
    try:
        response = _request(url, request_get=request_get)
    except Exception:
        row["detail_fetch_warning"] = "Pagina dettaglio non raggiungibile in questa scansione."
        return False
    detail_html = _response_text(response)
    detail_text = _text_from_html_content(detail_html)
    if source_exclusion_reason(source, title=row.get("title"), body_text=detail_text, url=url):
        row["detail_exclusion_reason"] = source_exclusion_reason(source, title=row.get("title"), body_text=detail_text, url=url)
        return False
    current_text = _clean_spaces(row.get("raw_text"))
    if detail_text:
        if not current_text:
            merged_text = detail_text
        elif detail_text.casefold() not in current_text.casefold():
            merged_text = _clean_spaces(f"{current_text}\n\n{detail_text}")
        else:
            merged_text = current_text
        if len(merged_text) >= len(current_text):
            row["raw_text"] = merged_text
            row["body_short"] = _truncate(merged_text)
    row["raw_html"] = detail_html[:20000]
    row["detail_http_status"] = int(getattr(response, "status_code", 200) or 0)
    attachments = _attachment_links(detail_html, url)
    if attachments:
        row["attachments_json"] = _merge_attachments(row.get("attachments_json"), attachments)
    return True


def _text_from_html_content(content: str) -> str:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError):
        return _clean_spaces(content)
    for node in tree.xpath("//script|//style|//noscript|//nav|//header|//footer|//form"):
        try:
            node.drop_tree()
        except Exception:
            continue
    main_nodes = tree.xpath("//main|//article|//*[@role='main']")
    root = main_nodes[0] if main_nodes else tree
    return _clean_spaces(" ".join(root.xpath(".//text()")) or root.text_content())


def _attachment_links(html_text: str, base_url: str) -> list[dict[str, str]]:
    try:
        tree = lxml_html.fromstring(html_text)
    except (ValueError, TypeError):
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in tree.xpath("//a[@href]"):
        href = _clean_spaces(anchor.attrib.get("href"))
        label = _clean_spaces(anchor.text_content())
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:")):
            continue
        absolute = _normalize_document_url(urljoin(base_url, href))
        if absolute in seen or not _looks_like_attachment(absolute, label):
            continue
        seen.add(absolute)
        rows.append({"title": label or _filename_from_url(absolute) or "Allegato", "url": absolute, "attachment_type": _file_type_from_url(absolute)})
        if len(rows) >= 8:
            break
    return rows


def _attachment_candidates(text: str, base_url: str) -> list[dict[str, str]]:
    return _attachment_links(text if "<" in text else f"<a href='{base_url}'>{text}</a>", base_url)


def _looks_like_attachment(url: str, label: str) -> bool:
    lower = f"{url} {label}".lower()
    path = urlsplit(url).path.lower()
    return path.endswith(ATTACHMENT_EXTENSIONS) or any(marker in lower for marker in ATTACHMENT_LABELS)


def _file_type_from_url(url: str) -> str:
    path = urlsplit(url).path.lower()
    for ext in ATTACHMENT_EXTENSIONS:
        if path.endswith(ext):
            return ext.lstrip(".")
    return ""


def _filename_from_url(url: str) -> str:
    return urlsplit(str(url or "")).path.rsplit("/", 1)[-1]


def _merge_attachments(current: Any, incoming: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = current if isinstance(current, list) else []
    by_url = {_clean_spaces(row.get("url")): dict(row) for row in rows if isinstance(row, dict)}
    for row in incoming:
        url = _clean_spaces(row.get("url"))
        if url:
            by_url[url] = {**by_url.get(url, {}), **row}
    return list(by_url.values())


def _cassazione_detail_url(url: str) -> bool:
    lowered = str(url or "").lower()
    return any(marker in lowered for marker in CASSAZIONE_DETAIL_URL_MARKERS) and "contentid=" in lowered


def _cassazione_latest_category_urls(base_url: str, content: str) -> list[str]:
    urls: list[str] = []

    def _push(value: str) -> None:
        absolute = _normalize_document_url(urljoin(base_url, value))
        if (
            absolute
            and absolute not in urls
            and any(marker in absolute.lower() for marker in CASSAZIONE_LATEST_CATEGORY_MARKERS)
        ):
            urls.append(absolute)

    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError):
        tree = None
    if tree is not None:
        for anchor in tree.xpath("//a[@href]"):
            _push(_clean_spaces(anchor.attrib.get("href")))
    for marker in CASSAZIONE_LATEST_CATEGORY_MARKERS:
        _push(f"https://www.cortedicassazione.it/it/{marker}")
    return urls


def _cassazione_detail_rows_from_html(source: dict[str, Any], page_url: str, content: str) -> list[dict[str, Any]]:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError):
        return []
    rows_by_url: dict[str, dict[str, Any]] = {}
    for anchor in tree.xpath("//a[@href]"):
        href = _clean_spaces(anchor.attrib.get("href"))
        absolute_url = _normalize_document_url(urljoin(page_url, href))
        if not _cassazione_detail_url(absolute_url):
            continue
        title = _clean_spaces(anchor.text_content())
        if not title or title.casefold().startswith("vai al documento"):
            title = _clean_spaces(" ".join(anchor.xpath("./ancestor::*[self::article or self::li or self::div][1]//a[1]//text()"))) or title
        row_text = _clean_spaces(" ".join(anchor.xpath("./ancestor::*[self::article or self::li or self::div][1]//text()"))) or title
        if len(title) < 8 and not row_text:
            continue
        rows_by_url[absolute_url] = {
            "external_id": _sha256(f"{source.get('code')}|{absolute_url}"),
            "source_url": absolute_url,
            "title": title,
            "published_at": _parse_pub_date(f"{title} {row_text}"),
            "raw_html": "",
            "raw_text": row_text,
            "body_short": _truncate(row_text or title),
        }
    return list(rows_by_url.values())


def _extract_cassazione_latest(source: dict[str, Any], base_html: str, *, request_get: RequestGet) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    max_items = _env_int("IUSENTRA_CASSAZIONE_LATEST_MAX_ITEMS", 20)
    category_pages = [(source["base_url"], base_html)]
    for page_url in _cassazione_latest_category_urls(source["base_url"], base_html):
        try:
            page_response = _request(page_url, request_get=request_get)
        except Exception:
            continue
        page_text = _response_text(page_response)
        if page_text:
            category_pages.append((page_url, page_text))
    seen_urls: set[str] = set()
    for page_url, page_text in category_pages:
        for row in _cassazione_detail_rows_from_html(source, page_url, page_text):
            detail_url = _clean_spaces(row.get("source_url"))
            if not detail_url or detail_url in seen_urls:
                continue
            seen_urls.add(detail_url)
            _merge_detail(source, row, detail_url, request_get=request_get)
            docs.append(row)
            if len(docs) >= max_items:
                break
        if len(docs) >= max_items:
            break
    return _merge_unique_documents(docs)


def _ckan_package_rows(payload: Any) -> list[dict[str, Any]]:
    result = payload.get("result") if isinstance(payload, dict) else {}
    if not isinstance(result, dict):
        return []
    if isinstance(result.get("results"), list):
        return [row for row in result["results"] if isinstance(row, dict)]
    if isinstance(result.get("packages"), list):
        return [row for row in result["packages"] if isinstance(row, dict)]
    if isinstance(result.get("resources"), list):
        return [{"title": result.get("title") or result.get("name"), "notes": result.get("notes"), "resources": result.get("resources")}]
    return []


def _extract_ckan_items(source: dict[str, Any], base_url: str, content: str, *, request_get: RequestGet) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    docs: list[dict[str, Any]] = []
    fetched_resources = 0
    for package in _ckan_package_rows(payload):
        package_id = _clean_spaces(package.get("id") or package.get("name"))
        package_title = _clean_spaces(package.get("title") or package.get("name") or package_id)
        package_notes = _clean_spaces(package.get("notes") or package.get("description"))
        package_date = _parse_pub_date(package.get("metadata_modified") or package.get("modified") or package.get("created") or package.get("metadata_created"))
        package_url = _clean_spaces(package.get("url") or "")
        resources = [row for row in list(package.get("resources") or []) if isinstance(row, dict)]
        if not resources:
            docs.append(_ckan_row(source, base_url, package_id, package_title, package_notes, package_date, package_url, {}, "dataset"))
            continue
        for resource in resources:
            row = _ckan_row(source, base_url, package_id, package_title, package_notes, package_date, package_url, resource, _clean_spaces(resource.get("format") or resource.get("mimetype") or resource.get("resource_type")))
            resource_url = _clean_spaces(row.get("resource_url") or row.get("source_url"))
            resource_format = _clean_spaces(row.get("resource_format")).lower()
            if fetched_resources < 20 and resource_url and ("json" in resource_format or resource_url.lower().endswith(".json")):
                try:
                    resource_response = _request(resource_url, request_get=request_get)
                    resource_text = _response_text(resource_response)
                except Exception:
                    resource_text = ""
                    row["resource_fetch_warning"] = "Risorsa JSON non raggiungibile durante questa scansione."
                if resource_text:
                    row["raw_text"] = _truncate(
                        f"{row.get('raw_text') or ''} Contenuto JSON acquisito: {resource_text}",
                        limit=20000,
                    )
                    row["body_short"] = _truncate(row.get("raw_text") or "")
                    row["resource_http_status"] = int(getattr(resource_response, "status_code", 200) or 0)
                    fetched_resources += 1
            docs.append(row)
    return _merge_unique_documents(docs)


def _ckan_row(
    source: dict[str, Any],
    base_url: str,
    package_id: str,
    package_title: str,
    package_notes: str,
    package_date: str,
    package_url: str,
    resource: dict[str, Any],
    resource_format: str,
) -> dict[str, Any]:
    resource_id = _clean_spaces(resource.get("id") or resource.get("name") or resource.get("url"))
    resource_name = _clean_spaces(resource.get("name") or resource.get("title") or resource_id)
    resource_url = _normalize_document_url(_clean_spaces(resource.get("url") or package_url or base_url))
    resource_date = _parse_pub_date(resource.get("last_modified") or resource.get("metadata_modified") or resource.get("created") or package_date)
    title = _clean_spaces(" - ".join(part for part in (package_title, resource_name) if part))
    body = _clean_spaces(
        " ".join(
            part
            for part in (
                package_notes,
                f"Dataset OpenGA: {package_title}" if package_title else "",
                f"Risorsa: {resource_name}" if resource_name else "",
                f"Formato: {resource_format}" if resource_format else "",
                f"URL: {resource_url}" if resource_url else "",
            )
            if part
        )
    )
    return {
        "external_id": _sha256(f"{source.get('code')}|{package_id}|{resource_id}|{resource_url}"),
        "source_url": resource_url,
        "title": title or resource_url or source.get("name") or base_url,
        "published_at": resource_date or package_date,
        "raw_html": "",
        "raw_text": body,
        "body_short": _truncate(body or title),
        "resource_format": resource_format,
        "resource_url": resource_url,
        "package_id": package_id,
        "package_title": package_title,
        "attachments_json": _attachment_links(f"<a href='{resource_url}'>{resource_name}</a>", resource_url),
    }


def _extract_pager_frames(content: str) -> list[str]:
    pages: list[str] = []
    for match in PAGER_FRAME_RE.finditer(str(content or "")):
        page = _clean_spaces(match.group("page"))
        if page and page not in pages and page != "1":
            pages.append(page)
    return pages


def _set_query_param(url: str, key: str, value: str) -> str:
    split = urlsplit(str(url or ""))
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query[str(key)] = str(value)
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(query), split.fragment))


def _merge_unique_documents(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered: dict[str, dict[str, Any]] = {}
    for row in documents:
        external_id = str(row.get("external_id") or "")
        if not external_id:
            external_id = _sha256(f"{row.get('source_url')}|{row.get('title')}|{row.get('published_at')}")
            row["external_id"] = external_id
        previous = ordered.get(external_id)
        if not previous:
            ordered[external_id] = row
            continue
        if len(_clean_spaces(row.get("raw_text"))) > len(_clean_spaces(previous.get("raw_text"))):
            previous.update(row)
    return list(ordered.values())


def _fallback_document(source: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "external_id": _sha256(f"{source['code']}|{source['base_url']}|empty"),
        "source_url": source["base_url"],
        "title": source["name"],
        "published_at": "",
        "raw_html": text[:20000],
        "raw_text": _truncate(text, limit=4000),
        "body_short": _truncate(text),
    }


def _apply_capability_metadata(source: dict[str, Any], row: dict[str, Any]) -> None:
    capability = get_source_capability(source.get("code"), category=source.get("category"))
    reason = source_exclusion_reason(
        source,
        title=row.get("title"),
        body_text=row.get("raw_text") or row.get("body_short"),
        url=row.get("source_url"),
    )
    row["source_capability_json"] = capability.to_dict()
    row["publication_destination"] = capability.publication_destination
    row["publication_destination_label"] = publication_destination_label(capability.publication_destination)
    row["rag_destination"] = capability.rag_destination
    row["jurisprudence_destination"] = capability.jurisprudence_destination
    row["source_relevance_policy"] = capability.relevance_policy
    row["source_exclusion_policy"] = capability.exclusion_policy
    row["source_exclusion_reason"] = reason
    if reason:
        row["fetch_status"] = "out_of_scope"
