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
from lxml.etree import ParserError

from pct.legal_update_source_capabilities import (
    get_source_capability,
    publication_destination_label,
    source_exclusion_reason,
)


RequestGet = Callable[..., Any]

HTML_DATE_RE = re.compile(r"\b([0-3]?\d/[01]?\d/[12]\d{3})\b")
PAGER_FRAME_RE = re.compile(r'parametriUrl\("(?P<element>[^"]+)",\s*"(?P<page>[^"]+)"\)')
ATTACHMENT_EXTENSIONS = (".pdf", ".xml", ".doc", ".docx", ".odt", ".rtf", ".txt", ".zip")
ATTACHMENT_LABELS = ("pdf", "allegato", "scarica", "download", "documento ufficiale")
CASSAZIONE_LATEST_SOURCE_CODE = "cassazione_ultime_sent_ord_questioni"
GAZZETTA_SOURCE_CODE = "gazzetta_ufficiale"
GAZZETTA_SERIE_GENERALE_URL = "https://www.gazzettaufficiale.it/30giorni/serie_generale"
INPS_MESSAGGI_SOURCE_CODE = "inps_messaggi"
INPS_CIRCOLARI_MESSAGGI_PARENT = "/content/dam/inps-site/it/scorporati/circolari-e-messaggi"
INPS_CIRCOLARI_MESSAGGI_API = "https://www.inps.it/content/scorporati/search/jcr:content.search.{selectors}.json"
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
    listing_url = _source_listing_url(source)
    response = _request(listing_url, request_get=request_get)
    content_type = _header(response, "content-type")
    text = _response_text(response)
    parser_type = _clean_spaces(source.get("parser_type")).lower()
    capability = get_source_capability(source.get("code"), category=source.get("category"))

    source_code = _clean_spaces(source.get("code")).lower()

    if source_code == GAZZETTA_SOURCE_CODE:
        docs = _extract_gazzetta_items(source, listing_url, text)
    elif source_code == INPS_MESSAGGI_SOURCE_CODE:
        docs = _extract_inps_circolari_messaggi_api(source, listing_url, text, tipo="Messaggio")
        docs = _fetch_detail_pages(source, docs, request_get=request_get)
    elif parser_type == "ckan_json" or capability.item_strategy == "ckan_package_resources":
        docs = _extract_ckan_items(source, listing_url, text, request_get=request_get)
    elif parser_type in {"feed", "rss", "atom"} or _looks_like_feed(text, content_type):
        docs = _extract_feed_items(source, listing_url, text, request_get=request_get)
    elif _clean_spaces(source.get("code")).lower() == CASSAZIONE_LATEST_SOURCE_CODE:
        docs = _extract_cassazione_latest(source, text, request_get=request_get)
    else:
        docs = _filter_source_documents(source, _extract_html_listing(source, listing_url, text))
        docs = _fetch_detail_pages(source, docs, request_get=request_get)
        for page in _extract_pager_frames(text):
            page_url = _set_query_param(listing_url, "frame3_item", page)
            try:
                page_response = _request(page_url, request_get=request_get)
            except Exception:
                continue
            page_docs = _extract_html_listing(source, page_url, _response_text(page_response))
            page_docs = _filter_source_documents(source, page_docs)
            docs.extend(_fetch_detail_pages(source, page_docs, request_get=request_get))
        docs = _filter_source_documents(source, _merge_unique_documents(docs))

    docs = _filter_source_documents(source, docs)

    if not docs and not _strict_no_fallback_source(source):
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
    if hasattr(response, "content"):
        content = bytes(response.content or b"")
        if content:
            candidates: list[str] = []
            header = _header(response, "content-type")
            charset_match = re.search(r"charset=([^;\s]+)", header, flags=re.I)
            for value in (
                getattr(response, "encoding", None),
                charset_match.group(1) if charset_match else "",
                getattr(response, "apparent_encoding", None),
                "utf-8",
                "windows-1252",
                "iso-8859-1",
            ):
                encoding = _clean_spaces(value).lower()
                if encoding and encoding not in candidates:
                    candidates.append(encoding)
            decoded = [_decode_candidate(content, encoding) for encoding in candidates]
            if decoded:
                return min(decoded, key=_decode_penalty)
    if hasattr(response, "text"):
        return str(response.text or "")
    return ""


def _decode_candidate(content: bytes, encoding: str) -> str:
    try:
        return content.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return content.decode("utf-8", errors="replace")


def _decode_penalty(text: str) -> tuple[int, int]:
    lowered = text.lower()
    mojibake = sum(
        lowered.count(marker)
        for marker in (
            "\u00e3",
            "\u00e2",
            "\u00c3",
            "\u00c2",
            "\u00e2\u20ac",
            "\u00e2\u20ac\u2122",
            "\u00ef\u00bf\u00bd",
            "\ufffd",
        )
    )
    return (mojibake, text.count("\ufffd"))


def _source_listing_url(source: dict[str, Any]) -> str:
    code = _clean_spaces(source.get("code")).lower()
    if code == GAZZETTA_SOURCE_CODE:
        return GAZZETTA_SERIE_GENERALE_URL
    if code == INPS_MESSAGGI_SOURCE_CODE:
        return _inps_circolari_messaggi_api_url(limit=20)
    return _clean_spaces(source.get("base_url"))


def _clean_spaces(value: Any) -> str:
    repaired = _repair_mojibake(str(value or ""))
    return " ".join(repaired.split()).strip()


def _repair_mojibake(text: str) -> str:
    if not text:
        return ""
    if not any(
        marker in text
        for marker in (
            "\u00c3",
            "\u00c2",
            "\u00e2\u20ac",
            "\u00e2\u20ac\u2122",
            "\u00e2\u20ac\u0153",
            "\u00ef\u00bf\u00bd",
            "\ufffd",
        )
    ):
        return text
    candidates = [text]
    for encoding in ("latin-1", "windows-1252"):
        try:
            candidates.append(text.encode(encoding, errors="strict").decode("utf-8", errors="replace"))
        except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
            continue
    return min(candidates, key=_decode_penalty)


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
        title = _clean_feed_title(source, item.findtext("title") or item.findtext("{*}title"))
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


def _clean_feed_title(source: dict[str, Any], value: Any) -> str:
    title = _clean_spaces(value)
    code = _clean_spaces(source.get("code")).lower()
    if code == "curia_cgue_rss":
        cleaned = re.sub(r"^\d+\/.+:\s*(?:null\s*-\s*)?", "", title, flags=re.I).strip()
        return cleaned or title
    return title


def _extract_html_listing(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError, ParserError):
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


def _extract_gazzetta_items(source: dict[str, Any], base_url: str, content: str) -> list[dict[str, Any]]:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError, ParserError):
        return []
    rows_by_key: dict[str, dict[str, Any]] = {}
    for anchor in tree.xpath("//a[@href]"):
        href = _clean_spaces(anchor.attrib.get("href"))
        label = _clean_spaces(anchor.text_content())
        if "downloadPdf" not in href and "pdfPaginato" not in href:
            continue
        absolute = _normalize_document_url(urljoin(base_url, href))
        params = dict(parse_qsl(urlsplit(absolute).query, keep_blank_values=True))
        issue_date = _clean_spaces(params.get("dataPubblicazioneGazzetta"))
        issue_number = _clean_spaces(params.get("numeroGazzetta"))
        issue_series = _clean_spaces(params.get("tipoSerie") or "SG")
        if not issue_date or not issue_number:
            continue
        key = "|".join(
            _clean_spaces(params.get(name))
            for name in (
                "dataPubblicazioneGazzetta",
                "numeroGazzetta",
                "tipoSerie",
                "tipoSupplemento",
                "numeroSupplemento",
                "progressivo",
                "edizione",
            )
        )
        download_url = _gazzetta_download_url(absolute, params)
        detail_url = _gazzetta_detail_url(absolute, params)
        title = _gazzetta_title(issue_date, issue_number, issue_series, params)
        body = _clean_spaces(
            f"{title}. Fascicolo ufficiale della Gazzetta Ufficiale, serie {issue_series}, "
            f"pubblicato il {_gazzetta_date_it(issue_date)}. Allegato PDF ufficiale disponibile."
        )
        row = {
            "external_id": _sha256(f"{source.get('code')}|{key}|{download_url}"),
            "source_url": detail_url,
            "title": title,
            "published_at": _gazzetta_iso_date(issue_date),
            "raw_html": "",
            "raw_text": body,
            "body_short": _truncate(body),
            "attachments_json": [
                {
                    "title": label if "criptato" not in label.lower() else "Download PDF",
                    "url": download_url,
                    "attachment_type": "pdf",
                }
            ],
        }
        existing = rows_by_key.get(key)
        if existing:
            existing_url = _clean_spaces((existing.get("attachments_json") or [{}])[0].get("url")).lower()
            incoming_url = download_url.lower()
            if "pdf.p7m" in incoming_url and "pdf.p7m" not in existing_url:
                continue
        rows_by_key[key] = row
    rows = list(rows_by_key.values())
    rows.sort(key=lambda row: row.get("published_at") or "", reverse=True)
    if not rows and "<article" in content.lower():
        return _extract_html_listing(source, base_url, content)
    return rows


def _extract_inps_circolari_messaggi_api(
    source: dict[str, Any],
    base_url: str,
    content: str,
    *,
    tipo: str,
) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return []
    rows = ((payload.get("data") or {}).get("results") or []) if isinstance(payload, dict) else []
    docs: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_type = _clean_spaces(row.get("tipo"))
        if row_type.lower() != tipo.lower():
            continue
        selector = _clean_spaces(row.get("selectors"))
        number = _clean_spaces(row.get("numero"))
        published = _clean_spaces(row.get("dataPubblicazione"))
        subject = _clean_spaces(row.get("oggetto"))
        if not selector or not number:
            continue
        title = f"{tipo} numero {number}"
        if published:
            title = f"{title} del {published}"
        detail_url = (
            "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
            f"dettaglio.{selector}.html"
        )
        body = _clean_spaces(f"{title}. {subject}")
        docs.append(
            {
                "external_id": _sha256(f"{source.get('code')}|{selector}"),
                "source_url": detail_url,
                "title": title,
                "published_at": _parse_pub_date(published),
                "raw_html": "",
                "raw_text": body,
                "body_short": _truncate(body),
                "attachments_json": [],
            }
        )
    return _merge_unique_documents(docs)


def _inps_circolari_messaggi_api_url(*, limit: int) -> str:
    selectors = ".".join(
        _clean_spaces(value).encode("utf-8").hex()
        for value in (
            INPS_CIRCOLARI_MESSAGGI_PARENT,
            "0",
            str(max(1, int(limit or 10))),
            "giorno",
            "DESC",
            "circolari-e-messaggi",
        )
    )
    return INPS_CIRCOLARI_MESSAGGI_API.format(selectors=selectors)


def _gazzetta_download_url(url: str, params: dict[str, str]) -> str:
    split = urlsplit(url)
    clean = {
        name: params.get(name)
        for name in (
            "dataPubblicazioneGazzetta",
            "numeroGazzetta",
            "tipoSerie",
            "tipoSupplemento",
            "numeroSupplemento",
            "progressivo",
            "estensione",
            "edizione",
        )
        if params.get(name)
    }
    clean.setdefault("tipoSupplemento", "GU")
    clean.setdefault("numeroSupplemento", "0")
    clean.setdefault("progressivo", "0")
    clean.setdefault("estensione", "pdf")
    clean.setdefault("edizione", "0")
    return urlunsplit((split.scheme, split.netloc, "/do/gazzetta/downloadPdf", urlencode(clean), ""))


def _gazzetta_detail_url(url: str, params: dict[str, str]) -> str:
    split = urlsplit(url)
    clean = {
        "dataPubblicazioneGazzetta": _gazzetta_iso_date(params.get("dataPubblicazioneGazzetta") or ""),
        "numeroGazzetta": params.get("numeroGazzetta") or "",
        "elenco30giorni": "true",
    }
    return urlunsplit((split.scheme, split.netloc, "/gazzetta/serie_generale/caricaDettaglio", urlencode(clean), ""))


def _gazzetta_title(issue_date: str, issue_number: str, issue_series: str, params: dict[str, str]) -> str:
    supplement = _clean_spaces(params.get("tipoSupplemento"))
    supplement_number = _clean_spaces(params.get("numeroSupplemento"))
    suffix = f" ({supplement} n. {supplement_number})" if supplement and supplement != "GU" and supplement_number else ""
    return f"Gazzetta Ufficiale - {_gazzetta_series_label(issue_series)} n. {issue_number} del {_gazzetta_date_it(issue_date)}{suffix}"


def _gazzetta_series_label(value: str) -> str:
    return {
        "SG": "Serie Generale",
        "1SS": "1a Serie Speciale",
        "2SS": "2a Serie Speciale",
        "3SS": "3a Serie Speciale",
        "4SS": "4a Serie Speciale",
        "5SS": "5a Serie Speciale",
    }.get((value or "").upper(), value or "Serie")


def _gazzetta_iso_date(value: str) -> str:
    text = _clean_spaces(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _gazzetta_date_it(value: str) -> str:
    text = _clean_spaces(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[6:8]}/{text[4:6]}/{text[0:4]}"
    return text


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


def _filter_source_documents(source: dict[str, Any], docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    code = _clean_spaces(source.get("code")).lower()
    if not docs:
        return []
    filtered: list[dict[str, Any]] = []
    for row in docs:
        reason = _source_specific_exclusion_reason(code, row)
        if reason:
            row["source_exclusion_reason"] = reason
            continue
        filtered.append(row)
    if code in {"agcom_provvedimenti", "anac_documenti", "garante_privacy"}:
        filtered.sort(key=lambda row: _source_document_score(code, row), reverse=True)
    return _dedupe_by_url(filtered)


def _dedupe_by_url(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in docs:
        key = _normalize_document_url(_clean_spaces(row.get("source_url"))) or _clean_spaces(row.get("external_id"))
        if not key:
            continue
        previous = rows.get(key)
        if not previous:
            rows[key] = row
            continue
        if _source_document_score(_clean_spaces(row.get("source_code")), row) >= _source_document_score(_clean_spaces(previous.get("source_code")), previous):
            if len(_clean_spaces(row.get("raw_text"))) >= len(_clean_spaces(previous.get("raw_text"))):
                rows[key] = row
    return list(rows.values())


def _source_specific_exclusion_reason(code: str, row: dict[str, Any]) -> str:
    blob = _clean_spaces(f"{row.get('title')} {row.get('raw_text')} {row.get('source_url')}").lower()
    url = _clean_spaces(row.get("source_url")).lower()
    if code == "agcom_provvedimenti":
        if "agcom.it/provvedimenti/" not in url and "/provvedimenti/" not in url:
            return "Link AGCOM di navigazione o servizio: non è un provvedimento."
        if any(marker in blob for marker in ("autorità trasparente", "quadro legislativo", "archivio dei provvedimenti")):
            return "Pagina AGCOM di navigazione: non è un provvedimento operativo."
        if not any(marker in blob for marker in ("delibera", "determina", "provvedimento", "sanzion", "controvers", "corecom", "tutela utenti", "diritto d'autore", "comunicazione")):
            return "Voce AGCOM senza estremi di provvedimento, sanzione o controversia."
    if code == "anac_documenti":
        if "anticorruzione.it/-/" not in url and "/-/" not in url:
            return "Link ANAC di navigazione o servizio: non è un documento."
        if not any(marker in blob for marker in ("delibera", "parere", "precontenzioso", "atto del presidente", "atto a firma", "comunicato", "bando tipo", "linee guida")):
            return "Voce ANAC senza estremi di delibera, parere, atto o comunicato operativo."
    if code == "garante_privacy":
        if "docweb-display/docweb" not in url:
            return "Link Garante di navigazione, social o servizio: non è una newsletter/provvedimento."
        if not any(marker in blob for marker in ("newsletter", "provvedimento", "sanzion", "privacy", "garante")):
            return "Voce Garante senza contenuto privacy operativo."
    if code == "corte_costituzionale":
        if "/scheda-pronuncia/" not in url:
            return "Link Corte costituzionale di navigazione o servizio: non è una scheda pronuncia."
        if not re.search(r"/scheda-pronuncia/\d{4}/\d+", url):
            return "Scheda Corte costituzionale senza estremi anno/numero della pronuncia."
        if not any(marker in blob for marker in ("sentenza", "ordinanza", "pronuncia", "deposito", "costituzional")):
            return "Voce Corte costituzionale senza contenuto di pronuncia."
    if code == "corte_conti":
        if "/home/documenti/" not in url:
            return "Link Corte dei conti di navigazione o servizio: non è un documento giurisdizionale."
        if not any(marker in url for marker in ("dettaglio", "sentenza", ".pdf")):
            return "Link Corte dei conti senza dettaglio sentenza o documento ufficiale."
        if not any(marker in blob for marker in ("sentenza", "sezione giurisdizionale", "responsabilità erariale", "giudizio di conto", "appalto")):
            return "Voce Corte dei conti senza contenuto giurisdizionale operativo."
    if code == "pst_giustizia_download":
        generic_pages = (
            "download.page",
            "documentation.page",
            "schede_pratiche.page",
            "area_riservata.page",
        )
        if any(url.endswith(marker) for marker in generic_pages):
            return "Pagina PST di navigazione tecnica: resta fuori dalla pubblicazione e non è un documento scaricabile."
        if not any(
            marker in blob
            for marker in (
                "deposito",
                "telematico",
                "pct",
                "specifiche",
                "schema",
                "manuale",
                "redattore",
                "pdf",
                ".zip",
                ".xml",
            )
        ):
            return "Download PST non collegato a deposito, specifiche o manuali operativi."
    if code == "inps_messaggi":
        title_url = _clean_spaces(f"{row.get('title')} {row.get('source_url')}").lower()
        if "messaggio-numero" not in title_url and "messaggio numero" not in title_url:
            return "Voce INPS diversa da messaggio operativo."
    if code == "inps_circolari":
        title_url = _clean_spaces(f"{row.get('title')} {row.get('source_url')}").lower()
        if "circolare-numero" not in title_url and "circolare numero" not in title_url:
            return "Voce INPS diversa da circolare operativa."
    return ""


def _source_document_score(code: str, row: dict[str, Any]) -> int:
    blob = _clean_spaces(f"{row.get('title')} {row.get('raw_text')} {row.get('source_url')}").lower()
    score = 0
    markers = {
        "agcom_provvedimenti": ("delibera", "determina", "provvedimento", "sanzion", "controvers", "corecom", "tutela utenti", "diritto d'autore"),
        "anac_documenti": ("delibera", "parere", "precontenzioso", "atto del presidente", "bando tipo", "linee guida"),
        "garante_privacy": ("newsletter", "provvedimento", "sanzion", "docweb"),
    }.get(code, ())
    for marker in markers:
        if marker in blob:
            score += 10
    if re.search(r"\b\d+/\d{2,4}\b|\bn\.\s*\d+", blob):
        score += 5
    if row.get("published_at"):
        score += 3
    return score


def _strict_no_fallback_source(source: dict[str, Any]) -> bool:
    if _clean_spaces(source.get("parser_type")).lower() in {"feed", "rss", "atom"}:
        return True
    return _clean_spaces(source.get("code")).lower() in {
        GAZZETTA_SOURCE_CODE,
        "agcom_provvedimenti",
        "anac_documenti",
        "corte_conti",
        "corte_costituzionale",
        "garante_privacy",
    }


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
    if _is_generic_link_title(row.get("title")):
        detail_title = _detail_title_from_html(detail_html)
        if detail_title:
            row["title"] = detail_title
    row["raw_html"] = detail_html[:20000]
    row["detail_http_status"] = int(getattr(response, "status_code", 200) or 0)
    attachments = _attachment_links(detail_html, url)
    if attachments:
        row["attachments_json"] = _merge_attachments(row.get("attachments_json"), attachments)
    if _is_generic_link_title(row.get("title")):
        attachment_title = _detail_title_from_attachments(row.get("attachments_json"))
        if attachment_title:
            row["title"] = attachment_title
    return True


def _is_generic_link_title(value: Any) -> bool:
    text = _clean_spaces(value).casefold()
    return text in {
        "corte dei conti",
        "corte costituzionale",
        "dettaglio documenti",
        "leggi di più",
        "leggi di piu",
        "menu a briciole",
        "visualizza la scheda",
        "apri scheda",
        "apri",
    }


def _detail_title_from_html(html_text: str) -> str:
    try:
        tree = lxml_html.fromstring(html_text)
    except (ValueError, TypeError, ParserError):
        return ""
    for selector in ("//main//h1", "//article//h1", "//h1", "//main//h2", "//article//h2", "//title"):
        values = [_clean_spaces(node.text_content()) for node in tree.xpath(selector)]
        for value in values:
            if value and not _is_generic_link_title(value):
                return value
    return ""


def _detail_title_from_attachments(payload: Any) -> str:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload or "[]")
        except json.JSONDecodeError:
            payload = []
    if not isinstance(payload, list):
        return ""
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = _clean_spaces(item.get("title") or item.get("label"))
        if not title:
            continue
        title = re.sub(r"\s*\[[^\]]*(?:pdf|kb)[^\]]*\]\s*$", "", title, flags=re.IGNORECASE).strip()
        if title and not _is_generic_link_title(title):
            return title
    return ""


def _text_from_html_content(content: str) -> str:
    try:
        tree = lxml_html.fromstring(content)
    except (ValueError, TypeError, ParserError):
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
    except (ValueError, TypeError, ParserError):
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
    if "<" not in str(text or ""):
        return []
    return _attachment_links(text, base_url)


def _looks_like_attachment(url: str, label: str) -> bool:
    lower = f"{url} {label}".lower()
    path = urlsplit(url).path.lower()
    query = urlsplit(url).query.lower()
    if "open data" in lower or "dati-e-bilanci/open-data" in lower:
        return False
    if path.endswith(ATTACHMENT_EXTENSIONS) or "downloadpdf" in path or "format=pdf" in query or "estensione=pdf" in query:
        return True
    return any(marker in lower for marker in ATTACHMENT_LABELS)


def _file_type_from_url(url: str) -> str:
    path = urlsplit(url).path.lower()
    query = urlsplit(url).query.lower()
    if "downloadpdf" in path or "format=pdf" in query or "estensione=pdf" in query:
        return "pdf"
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
    except (ValueError, TypeError, ParserError):
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
    except (ValueError, TypeError, ParserError):
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
    max_items = _env_int("IUSENTRA_CASSAZIONE_LATEST_MAX_ITEMS", 5)
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
