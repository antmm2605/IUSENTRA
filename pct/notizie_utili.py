from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import html as html_module
import re
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests
from lxml import html as lxml_html

from pct.legal_update_source_parsers import fetch_source_documents


RequestGet = Callable[..., Any]

GIUSTIZIA_URL = (
    "https://www.giustizia.it/giustizia/page/it/"
    "decreti_circolari_direttive_provvedimenti_note"
    "?facetNode_1=1_1%282026%29&selectedNode=1_1%282026%29"
)
CNF_URL = "https://www.consiglionazionaleforense.it/"
CASSA_FORENSE_URL = "https://www.cfnews.it/"
GAZZETTA_URL = "https://www.gazzettaufficiale.it/30giorni/serie_generale"
PST_GIUSTIZIA_URL = "https://pst.giustizia.it/PST/it/news.page"
CASSAZIONE_URL = "https://www.cortedicassazione.it/it/ultime_dalla_corte.page"

SOURCE_DEFINITIONS: tuple[dict[str, str], ...] = (
    {"id": "giustizia", "label": "Giustizia", "url": GIUSTIZIA_URL},
    {"id": "pst_giustizia", "label": "PST Giustizia", "url": PST_GIUSTIZIA_URL},
    {"id": "cnf", "label": "CNF", "url": CNF_URL},
    {"id": "cassa_forense", "label": "Cassa Forense", "url": CASSA_FORENSE_URL},
    {"id": "gazzetta_ufficiale", "label": "Gazzetta Ufficiale", "url": GAZZETTA_URL},
    {"id": "cassazione", "label": "Corte di Cassazione", "url": CASSAZIONE_URL},
)

_MONTHS = {
    "gennaio": 1,
    "gen": 1,
    "febbraio": 2,
    "feb": 2,
    "marzo": 3,
    "mar": 3,
    "aprile": 4,
    "apr": 4,
    "maggio": 5,
    "mag": 5,
    "giugno": 6,
    "giu": 6,
    "luglio": 7,
    "lug": 7,
    "agosto": 8,
    "ago": 8,
    "settembre": 9,
    "set": 9,
    "ottobre": 10,
    "ott": 10,
    "novembre": 11,
    "nov": 11,
    "dicembre": 12,
    "dic": 12,
}
_ITALIAN_DATE_RE = re.compile(
    r"\b([0-3]?\d)\s+(" + "|".join(_MONTHS) + r")\.?\s+(20\d{2})\b",
    re.IGNORECASE,
)
_NUMERIC_DATE_RE = re.compile(r"\b([0-3]?\d)[/.-]([01]?\d)[/.-]((?:20)?\d{2})\b")
_ISO_DATE_RE = re.compile(r"\b(20\d{2})-([01]\d)-([0-3]\d)\b")
_ARTICLE_PATHS = ("/diritto/", "/avvocatura/", "/assistenza/", "/societa-e-impresa/")
_ALLOWED_HOSTS = {
    "www.giustizia.it",
    "giustizia.it",
    "pst.giustizia.it",
    "www.consiglionazionaleforense.it",
    "consiglionazionaleforense.it",
    "www.cfnews.it",
    "cfnews.it",
    "www.gazzettaufficiale.it",
    "gazzettaufficiale.it",
    "www.cortedicassazione.it",
    "cortedicassazione.it",
}
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; IUSENTRA/1.0; +https://app.iusentra.it)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9",
}


def _clean_text(value: Any) -> str:
    return " ".join(html_module.unescape(str(value or "")).replace("\ufffd", "").split()).strip()


def _validate_source_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        raise ValueError("Fonte non ammessa.")
    return url


def _response(request_get: RequestGet, url: str, *, timeout: int = 12):
    current_url = _validate_source_url(url)
    for _hop in range(4):
        try:
            response = request_get(
                current_url,
                headers=_HEADERS,
                timeout=timeout,
                allow_redirects=False,
            )
        except TypeError:
            response = request_get(current_url)

        status_code = int(getattr(response, "status_code", 200) or 200)
        location = str(getattr(response, "headers", {}).get("Location") or "").strip()
        if status_code in {301, 302, 303, 307, 308}:
            if not location:
                raise ValueError("La fonte ha restituito un reindirizzamento non valido.")
            try:
                current_url = _validate_source_url(urljoin(current_url, location))
            except ValueError as exc:
                raise ValueError(
                    "La fonte ha reindirizzato verso un indirizzo non ammesso."
                ) from exc
            continue

        final_url = str(getattr(response, "url", "") or current_url)
        try:
            _validate_source_url(final_url)
        except ValueError as exc:
            raise ValueError(
                "La fonte ha reindirizzato verso un indirizzo non ammesso."
            ) from exc
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        return response
    raise ValueError("La fonte ha superato il numero massimo di reindirizzamenti ammessi.")


def _content_bytes(response: Any) -> bytes:
    content = getattr(response, "content", b"")
    if isinstance(content, bytes) and content:
        return content
    return str(getattr(response, "text", "") or "").encode("utf-8")


def _tree(request_get: RequestGet, url: str):
    return lxml_html.fromstring(_content_bytes(_response(request_get, url)))


def _date_iso(value: Any) -> str:
    text = _clean_text(value)
    iso = _ISO_DATE_RE.search(text)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    numeric = _NUMERIC_DATE_RE.search(text)
    if numeric:
        year = int(numeric.group(3))
        if year < 100:
            year += 2000
        return f"{year:04d}-{int(numeric.group(2)):02d}-{int(numeric.group(1)):02d}"
    italian = _ITALIAN_DATE_RE.search(text)
    if italian:
        return f"{italian.group(3)}-{_MONTHS[italian.group(2).lower()]:02d}-{int(italian.group(1)):02d}"
    return ""


def _meta_content(tree: Any, *keys: str) -> str:
    wanted = {key.casefold() for key in keys}
    for node in tree.xpath("//meta[@content]"):
        name = _clean_text(node.attrib.get("property") or node.attrib.get("name")).casefold()
        if name in wanted:
            return _clean_text(node.attrib.get("content"))
    return ""


def _summary(value: Any, *, limit: int = 420) -> str:
    text = _clean_text(value)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."


def _item(
    *,
    source_id: str,
    source_name: str,
    title: str,
    url: str,
    published_at: str,
    summary: str,
) -> dict[str, Any]:
    digest = hashlib.sha256(f"{source_id}|{url}".encode("utf-8")).hexdigest()[:24]
    clean_summary = _summary(summary or title)
    return {
        "id": f"official_{digest}",
        "slug": f"{source_id}-{digest[:12]}",
        "title": _clean_text(title),
        "short_summary": clean_summary,
        "content": clean_summary,
        "news_type": "informazione_professionale",
        "published_at": published_at,
        "source_name": source_name,
        "source_code": source_id,
        "source_category": "informazione_professionale",
        "source_url": url,
        "matter_name": "",
        "submatter_name": "",
        "publication_status": "published",
    }


def _collect_gazzetta(request_get: RequestGet, *, limit: int) -> list[dict[str, Any]]:
    source = {
        "name": "Gazzetta Ufficiale",
        "code": "gazzetta_ufficiale",
        "category": "normativa",
        "base_url": "https://www.gazzettaufficiale.it/",
        "parser_type": "html",
    }
    documents = fetch_source_documents(source, request_get=request_get)
    return [
        _item(
            source_id="gazzetta_ufficiale",
            source_name="Gazzetta Ufficiale",
            title=row.get("title") or "Gazzetta Ufficiale",
            url=row.get("source_url") or GAZZETTA_URL,
            published_at=_date_iso(row.get("published_at")),
            summary=row.get("body_short") or row.get("raw_text") or row.get("title"),
        )
        for row in documents
        if _date_iso(row.get("published_at"))
    ][:limit]


def _collect_giustizia(request_get: RequestGet, *, limit: int) -> list[dict[str, Any]]:
    tree = _tree(request_get, GIUSTIZIA_URL)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for anchor in tree.xpath("//a[@href]"):
        href = _clean_text(anchor.attrib.get("href"))
        title = _clean_text(anchor.text_content())
        if "provvedimento_ministeriale_selezionato" not in href or not title:
            continue
        if not re.match(r"^(?:Decreto|Circolare|Direttiva|Provvedimento)\b", title, re.IGNORECASE):
            continue
        url = urljoin(GIUSTIZIA_URL, href)
        published_at = _date_iso(title)
        if not published_at or url in seen:
            continue
        seen.add(url)
        rows.append(_item(
            source_id="giustizia",
            source_name="Giustizia",
            title=title,
            url=url,
            published_at=published_at,
            summary=title,
        ))
    rows.sort(key=lambda row: row["published_at"], reverse=True)
    return rows[:limit]


def _detail_item(
    request_get: RequestGet,
    *,
    source_id: str,
    source_name: str,
    title: str,
    url: str,
) -> dict[str, Any] | None:
    tree = _tree(request_get, url)
    description = _meta_content(tree, "description", "og:description")
    date_text = _meta_content(
        tree,
        "article:published_time",
        "article:modified_time",
        "og:updated_time",
        "date",
    )
    body_nodes = tree.xpath("//main|//article|//*[@role='main']")
    body = _clean_text((body_nodes[0] if body_nodes else tree).text_content())
    title_index = body.casefold().find(title.casefold())
    local_text = body[title_index:title_index + 1100] if title_index >= 0 else body[:1100]
    published_at = _date_iso(date_text) or _date_iso(local_text)
    if not published_at:
        return None
    fallback = local_text
    if title and fallback.casefold().startswith(title.casefold()):
        fallback = fallback[len(title):].strip(" -:")
    return _item(
        source_id=source_id,
        source_name=source_name,
        title=title,
        url=url,
        published_at=published_at,
        summary=description or fallback or title,
    )


def _collect_detail_source(
    request_get: RequestGet,
    *,
    source_id: str,
    source_name: str,
    base_url: str,
    candidate_builder: Callable[[Any], list[tuple[str, str]]],
    limit: int,
) -> list[dict[str, Any]]:
    tree = _tree(request_get, base_url)
    candidates = candidate_builder(tree)[: max(limit + 3, limit)]
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, max(1, len(candidates)))) as executor:
        futures = [
            executor.submit(
                _detail_item,
                request_get,
                source_id=source_id,
                source_name=source_name,
                title=title,
                url=url,
            )
            for title, url in candidates
        ]
        for future in as_completed(futures):
            try:
                row = future.result()
            except Exception:
                row = None
            if row:
                rows.append(row)
    rows.sort(key=lambda row: row["published_at"], reverse=True)
    return rows[:limit]


def _cnf_candidates(tree: Any) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in tree.xpath("//a[@href]"):
        href = _clean_text(anchor.attrib.get("href"))
        title = _clean_text(anchor.text_content())
        if "/web/cnf-news/-/" not in href or len(title) < 18:
            continue
        url = urljoin(CNF_URL, href)
        if url in seen:
            continue
        seen.add(url)
        rows.append((title, url))
    return rows


def _cassa_candidates(tree: Any) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for anchor in tree.xpath("//a[@href]"):
        href = _clean_text(anchor.attrib.get("href"))
        title = _clean_text(anchor.text_content())
        parsed = urlparse(urljoin(CASSA_FORENSE_URL, href))
        if not any(parsed.path.startswith(path) for path in _ARTICLE_PATHS):
            continue
        if parsed.path.rstrip("/") in {path.rstrip("/") for path in _ARTICLE_PATHS} or len(title) < 18:
            continue
        url = urljoin(CASSA_FORENSE_URL, href)
        if url in seen:
            continue
        seen.add(url)
        rows.append((title, url))
    return rows


def _collect_pst_giustizia(request_get: RequestGet, *, limit: int) -> list[dict[str, Any]]:
    tree = _tree(request_get, PST_GIUSTIZIA_URL)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    cards = tree.xpath(
        "//*[contains(concat(' ', normalize-space(@class), ' '), ' card-body ')]"
    )
    for card in cards:
        heading = card.xpath(".//*[self::h2 or self::h3 or self::h4 or self::h5][1]")
        title = _clean_text(heading[0].text_content()) if heading else ""
        anchors = card.xpath(".//a[@href]")
        detail = next(
            (
                anchor for anchor in anchors
                if any(
                    label in _clean_text(anchor.text_content()).casefold()
                    for label in ("leggi di pi", "leggi di più")
                )
            ),
            anchors[0] if anchors else None,
        )
        if not title or detail is None:
            continue
        url = urljoin(PST_GIUSTIZIA_URL, _clean_text(detail.attrib.get("href")))
        published_at = _date_iso(card.text_content())
        if not published_at or url in seen:
            continue
        paragraphs = [_clean_text(node.text_content()) for node in card.xpath(".//p")]
        summary = next((value for value in paragraphs if len(value) > 24), title)
        seen.add(url)
        rows.append(_item(
            source_id="pst_giustizia",
            source_name="PST Giustizia",
            title=title,
            url=url,
            published_at=published_at,
            summary=summary,
        ))
    rows.sort(key=lambda row: row["published_at"], reverse=True)
    return rows[:limit]


def _collect_cassazione(request_get: RequestGet, *, limit: int) -> list[dict[str, Any]]:
    tree = _tree(request_get, CASSAZIONE_URL)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for heading in tree.xpath("//main//h3|//*[@id='main']//h3|//h3"):
        anchors = heading.xpath(".//a[@href]")
        if not anchors:
            continue
        anchor = anchors[0]
        href = _clean_text(anchor.attrib.get("href"))
        title = _clean_text(heading.text_content())
        if not href or len(title) < 16:
            continue
        url = urljoin(CASSAZIONE_URL, href)
        parsed = urlparse(url)
        if (parsed.hostname or "").lower() not in {"www.cortedicassazione.it", "cortedicassazione.it"}:
            continue
        container = heading.xpath("ancestor::*[self::article or self::div][1]")
        context = _clean_text((container[0] if container else heading).text_content())
        published_at = _date_iso(title) or _date_iso(context)
        if not published_at or url in seen:
            continue
        seen.add(url)
        summary = context
        if summary.casefold().startswith(title.casefold()):
            summary = summary[len(title):].strip(" -:")
        rows.append(_item(
            source_id="cassazione",
            source_name="Corte di Cassazione",
            title=title,
            url=url,
            published_at=published_at,
            summary=summary or title,
        ))
    rows.sort(key=lambda row: row["published_at"], reverse=True)
    return rows[:limit]


def _source_collectors(request_get: RequestGet, *, limit: int) -> dict[str, Callable[[], list[dict[str, Any]]]]:
    return {
        "giustizia": lambda: _collect_giustizia(request_get, limit=limit),
        "pst_giustizia": lambda: _collect_pst_giustizia(request_get, limit=limit),
        "cnf": lambda: _collect_detail_source(
            request_get,
            source_id="cnf",
            source_name="CNF",
            base_url=CNF_URL,
            candidate_builder=_cnf_candidates,
            limit=limit,
        ),
        "cassa_forense": lambda: _collect_detail_source(
            request_get,
            source_id="cassa_forense",
            source_name="Cassa Forense",
            base_url=CASSA_FORENSE_URL,
            candidate_builder=_cassa_candidates,
            limit=limit,
        ),
        "gazzetta_ufficiale": lambda: _collect_gazzetta(request_get, limit=limit),
        "cassazione": lambda: _collect_cassazione(request_get, limit=limit),
    }


def refresh_notizie_utili(
    *,
    request_get: RequestGet = requests.get,
    limit_per_source: int = 12,
) -> dict[str, Any]:
    """Aggiorna in modo limitato le fonti professionali senza avviare la pipeline editoriale."""

    limit = max(1, min(int(limit_per_source or 12), 24))
    definitions = {row["id"]: row for row in SOURCE_DEFINITIONS}
    collectors = _source_collectors(request_get, limit=limit)
    items: list[dict[str, Any]] = []
    states: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=len(collectors)) as executor:
        futures = {executor.submit(collector): source_id for source_id, collector in collectors.items()}
        for future in as_completed(futures):
            source_id = futures[future]
            definition = definitions[source_id]
            try:
                rows = future.result()
                if not rows:
                    raise RuntimeError("La fonte non ha restituito aggiornamenti leggibili.")
                items.extend(rows)
                states[source_id] = {
                    **definition,
                    "ok": True,
                    "count": len(rows),
                    "latestPublishedAt": max((row["published_at"] for row in rows), default=""),
                    "message": "",
                }
            except Exception as exc:
                states[source_id] = {
                    **definition,
                    "ok": False,
                    "count": 0,
                    "latestPublishedAt": "",
                    "message": _summary(str(exc), limit=180),
                }

    unique = {str(row["id"]): row for row in items if row.get("id") and row.get("published_at")}
    ordered_items = sorted(
        unique.values(),
        key=lambda row: (str(row.get("published_at") or ""), str(row.get("title") or "")),
        reverse=True,
    )
    refreshed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return {
        "items": ordered_items,
        "sources": [states[row["id"]] for row in SOURCE_DEFINITIONS],
        "refreshedAt": refreshed_at,
    }
