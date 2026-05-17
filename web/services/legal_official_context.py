"""Lettura breve e governata di contesto da fonti ufficiali.

Il servizio e' pensato per essere chiamabile da superfici interattive: usa
timeout stretti, limita i byte scaricati e restituisce sempre un payload
controllato anche quando la fonte esterna non risponde.
"""

from __future__ import annotations

import html
import io
import os
import re
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests

try:  # pragma: no cover - fallback coperto senza forzare dipendenze opzionali.
    from pct.legal_update_web_verification import (
        _is_recognized_official_url as is_recognized_official_url,
    )
    from pct.legal_update_web_verification import extract_official_attachment_confirmations
except Exception:  # pragma: no cover
    extract_official_attachment_confirmations = None
    is_recognized_official_url = None

try:  # pragma: no cover - il fallback e' coperto senza forzare dipendenze.
    from lxml import etree
    from lxml import html as lxml_html
except Exception:  # pragma: no cover
    etree = None
    lxml_html = None


DEFAULT_TIMEOUT: tuple[float, float] = (2.0, 5.0)
DEFAULT_MAX_BYTES = 1_250_000
DEFAULT_CONTEXT_LIMIT = 1800
USER_AGENT = "IUSENTRA-Official-Context/1.0 (+https://iusentra.local)"
_ATTACHMENT_READ_DISABLED = {"0", "false", "no", "off"}

_SPACE_RE = re.compile(r"\s+")
_TAG_RE = re.compile(r"<[^>]+>")
_SENTENCE_RE = re.compile(r"(?<=[.!?;:])\s+|\n+")
_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9]{3,}")
_STOPWORDS = {
    "alla",
    "alle",
    "anche",
    "come",
    "con",
    "dalla",
    "delle",
    "del",
    "della",
    "gli",
    "nel",
    "nella",
    "per",
    "che",
    "sul",
    "sulla",
    "tra",
    "una",
    "uno",
    "ufficiale",
    "gazzetta",
    "decreto",
    "legislativo",
}
_NOISE_MARKERS = (
    "cookie",
    "privacy",
    "javascript",
    "accedi",
    "registrati",
    "newsletter",
    "menu",
    "seguici",
)


def build_official_context(
    url: str,
    query: str = "",
    *,
    request_get: Callable[..., Any] | None = None,
    timeout: float | tuple[float, float] = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    context_limit: int = DEFAULT_CONTEXT_LIMIT,
) -> dict[str, Any]:
    """Scarica una fonte ufficiale e restituisce contesto operativo pulito.

    La funzione non propaga eccezioni di rete o parsing: in caso di timeout,
    HTTP non valido o contenuto non leggibile torna un payload incompleto con
    avvisi espliciti.
    """

    warnings: list[str] = []
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return _empty_payload(["URL ufficiale non valido o non supportato."])
    if not _recognized_official_url(url):
        return _empty_payload(["Fonte non inclusa nel catalogo dei domini ufficiali riconosciuti."])

    fetch = request_get or requests.get
    try:
        response = _fetch_recognized_official_response(fetch, url, timeout=timeout)
        if response is None:
            return _empty_payload(["La fonte ufficiale rimanda a un dominio non riconosciuto."])
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 200 or status_code >= 400:
            return _empty_payload([f"Fonte ufficiale non disponibile: HTTP {status_code}."])

        headers = _headers(response)
        content_type = headers.get("content-type", "")
        body, truncated = _read_limited_response(response, max_bytes=max_bytes)
        if truncated:
            warnings.append("Contenuto ufficiale scaricato solo in anteprima per limite dimensione.")
        if not body:
            return _empty_payload(["Fonte ufficiale raggiunta ma senza contenuto leggibile."])
    except requests.Timeout:
        return _empty_payload(["Fonte ufficiale non raggiunta entro il tempo massimo."])
    except requests.RequestException as exc:
        return _empty_payload([f"Fonte ufficiale non raggiungibile: {_short(str(exc), 180)}."])
    except Exception as exc:
        return _empty_payload([f"Lettura della fonte ufficiale non completata: {_short(str(exc), 180)}."])

    final_url = getattr(response, "url", url) or url
    if not _recognized_official_url(final_url):
        return _empty_payload(["La fonte ufficiale rimanda a un dominio non riconosciuto."])
    text, extraction_warnings = _extract_text(body, content_type, final_url)
    warnings.extend(extraction_warnings)
    text = _with_official_attachment_text(
        text,
        body,
        content_type,
        final_url,
        timeout=timeout,
        max_bytes=max_bytes,
    )
    clean_text = _normalize(text)
    if not clean_text:
        return _empty_payload(warnings + ["Nessun testo utile estratto dalla fonte ufficiale."])

    selected = _select_passages(clean_text, query, limit=context_limit)
    if not selected:
        selected = _short(clean_text, context_limit)
    summary = _summary(selected, query)
    key_points = _key_points(selected, query)
    checks = _operational_checks(selected, query)
    completed = len(selected) >= 120 and not any("non estratto" in warning.lower() for warning in warnings)

    return {
        "officialContext": selected,
        "contextSummary": summary,
        "keyPoints": key_points,
        "operationalChecks": checks,
        "contextCompleted": completed,
        "warnings": warnings,
    }


def _empty_payload(warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "officialContext": "",
        "contextSummary": "",
        "keyPoints": [],
        "operationalChecks": [
            "Riprova più tardi o apri la fonte ufficiale indicata prima di usare il riferimento in un atto."
        ],
        "contextCompleted": False,
        "warnings": list(warnings or []),
    }


def _recognized_official_url(url: str) -> bool:
    if is_recognized_official_url is None:
        return False
    try:
        return bool(is_recognized_official_url(url))
    except Exception:
        return False


def _fetch_recognized_official_response(fetch: Callable[..., Any], url: str, *, timeout: float | tuple[float, float]) -> Any | None:
    current_url = url
    for _ in range(4):
        response = fetch(
            current_url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/pdf,application/xml,text/xml,text/plain,*/*;q=0.8",
            },
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code not in {301, 302, 303, 307, 308}:
            return response
        location = _normalize((getattr(response, "headers", {}) or {}).get("location", ""))
        if not location:
            return response
        next_url = urljoin(current_url, location)
        if not _recognized_official_url(next_url):
            return None
        current_url = next_url
    return None


def _headers(response: Any) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in (getattr(response, "headers", {}) or {}).items()}


def _read_limited_response(response: Any, *, max_bytes: int) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    truncated = False
    iterator = getattr(response, "iter_content", None)
    if callable(iterator):
        for chunk in iterator(chunk_size=65536):
            if not chunk:
                continue
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8", errors="ignore")
            remaining = max(0, max_bytes - total)
            if len(chunk) > remaining:
                chunks.append(chunk[:remaining])
                truncated = True
                break
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_bytes:
                truncated = True
                break
        return b"".join(chunks), truncated

    content = getattr(response, "content", b"") or b""
    if isinstance(content, str):
        content = content.encode("utf-8", errors="ignore")
    return content[:max_bytes], len(content) > max_bytes


def _extract_text(data: bytes, content_type: str, url: str) -> tuple[str, list[str]]:
    kind = _content_kind(content_type, url)
    if kind == "pdf":
        return _extract_pdf(data)
    if kind == "xml":
        return _extract_xml(data)
    if kind == "html":
        return _extract_html(_decode(data))
    return _decode(data), []


def _with_official_attachment_text(
    page_text: str,
    body: bytes,
    content_type: str,
    url: str,
    *,
    timeout: float | tuple[float, float],
    max_bytes: int,
) -> str:
    if extract_official_attachment_confirmations is None:
        return page_text
    if _content_kind(content_type, url) != "html":
        return page_text
    if str(os.getenv("IUSENTRA_LEGAL_VERIFICATION_READ_ATTACHMENTS", "1")).strip().lower() in _ATTACHMENT_READ_DISABLED:
        return page_text
    try:
        attachment_timeout = int(timeout[1] if isinstance(timeout, tuple) else timeout)
        confirmations = extract_official_attachment_confirmations(
            _decode(body),
            url,
            timeout=max(1, attachment_timeout),
            max_bytes=max(256_000, min(max_bytes, 5_000_000)),
        )
    except Exception:
        return page_text
    sections = [page_text]
    for confirmation in confirmations[:3]:
        excerpt = _normalize(confirmation.get("text_excerpt") or confirmation.get("excerpt"))
        title = _normalize(confirmation.get("title") or "allegato ufficiale")
        if excerpt:
            sections.append(f"Allegato ufficiale {title}: {excerpt}")
    return " ".join(section for section in sections if section)


def _content_kind(content_type: str, url: str) -> str:
    marker = f"{content_type} {url}".lower()
    if "pdf" in marker or marker.endswith(".pdf"):
        return "pdf"
    if "xml" in marker or marker.endswith(".xml") or marker.endswith(".xsd"):
        return "xml"
    if "html" in marker or "<html" in marker:
        return "html"
    return "text"


def _decode(data: bytes) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _extract_html(payload: str) -> tuple[str, list[str]]:
    if lxml_html is not None:
        try:
            root = lxml_html.fromstring(payload)
            for element in root.xpath("//script|//style|//noscript|//nav|//footer"):
                parent = element.getparent()
                if parent is not None:
                    parent.remove(element)
            return _normalize(" ".join(root.xpath("//body//text()") or root.xpath("//text()"))), []
        except Exception:
            pass
    return _normalize(html.unescape(_TAG_RE.sub(" ", payload))), []


def _extract_xml(data: bytes) -> tuple[str, list[str]]:
    if etree is not None:
        try:
            parser = etree.XMLParser(recover=True, resolve_entities=False, no_network=True)
            root = etree.fromstring(data, parser=parser)
            return _normalize(" ".join(root.xpath(".//text()"))), []
        except Exception:
            pass
    return _normalize(_decode(data)), ["XML ufficiale letto con parser di compatibilità."]


def _extract_pdf(data: bytes) -> tuple[str, list[str]]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages[:25])
        return _normalize(text), []
    except Exception as exc:
        return "", [f"PDF ufficiale non estratto automaticamente: {_short(str(exc), 160)}."]


def _normalize(value: Any) -> str:
    return _SPACE_RE.sub(" ", html.unescape(str(value or ""))).strip()


def _sentences(text: str) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    pending_heading = ""
    prepared = _prepare_sentence_text(text)
    for raw in _SENTENCE_RE.split(prepared or ""):
        sentence = _normalize(raw).strip(" -")
        sentence = _restore_sentence_text(sentence)
        if 8 <= len(sentence) < 45 and re.search(
            r"\bart\.|\barticolo\b|entrata in vigore|oggetto\b|allegato ufficiale", sentence.lower()
        ):
            pending_heading = f"{pending_heading}. {sentence}".strip(". ") if pending_heading else sentence
            continue
        if pending_heading:
            sentence = f"{pending_heading}. {sentence}".strip()
            pending_heading = ""
        if len(sentence) < 35 or len(sentence) > 700:
            continue
        lower = sentence.lower()
        if any(marker in lower for marker in _NOISE_MARKERS):
            continue
        key = lower[:160]
        if key in seen:
            continue
        seen.add(key)
        rows.append(sentence)
    return rows


def _prepare_sentence_text(text: Any) -> str:
    prepared = str(text or "")
    replacements = (
        (r"\.(pdf|xml|docx?|html?|txt)\b", r"__DOT__\1"),
        (r"\bD\.\s*Lgs\.", "D Lgs"),
        (r"\bD\.\s*L\.", "D L"),
        (r"\bD\.\s*M\.", "D M"),
        (r"\bD\.\s*P\.\s*R\.", "D P R"),
        (r"\bArt\.", "Articolo"),
        (r"\bart\.", "articolo"),
        (r"\bn\.\s*", "n__DOT__ "),
    )
    for pattern, replacement in replacements:
        prepared = re.sub(pattern, replacement, prepared, flags=re.IGNORECASE)
    return prepared


def _restore_sentence_text(text: str) -> str:
    return text.replace("n__DOT__", "n.").replace("__DOT__", ".")


def _tokens(*values: Any) -> list[str]:
    found: list[str] = []
    for value in values:
        for token in _WORD_RE.findall(_normalize(value).lower()):
            if token not in _STOPWORDS and token not in found:
                found.append(token)
    return found


def _select_passages(text: str, query: str, *, limit: int) -> str:
    sentences = _sentences(text)
    if not sentences:
        return _short(text, limit)
    tokens = _tokens(query)
    scored: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(sentences):
        lower = sentence.lower()
        score = sum(3 for token in tokens if token in lower)
        if re.search(r"\bart\.|\barticolo\b|\bcomma\b|\bentrata in vigore\b", lower):
            score += 2
        if re.search(r"\bdecreto legislativo\b|\bd\.lgs\.|\bgazzetta ufficiale\b", lower):
            score += 2
        if re.search(r"\ballegato ufficiale\b|\bpdf\b|\bxml\b", lower):
            score += 2
        if score:
            scored.append((score, -index, sentence))
    chosen = [row[2] for row in sorted(scored, reverse=True)[:5]] or sentences[:5]
    context = ""
    for sentence in chosen:
        candidate = f"{context} {sentence}".strip()
        if len(candidate) > limit:
            break
        context = candidate
    return context or _short(" ".join(chosen), limit)


def _summary(context: str, query: str) -> str:
    sentences = _sentences(context)
    base = " ".join(sentences[:2]) if sentences else context
    if query and base:
        return _short(f"{_normalize(query)}: {base}", 520)
    return _short(base, 520)


def _key_points(context: str, query: str) -> list[str]:
    points: list[str] = []
    if query:
        points.append(f"Riferimento cercato: {_short(query, 180)}")
    for sentence in _sentences(context):
        if len(points) >= 5:
            break
        cleaned = _short(sentence, 260)
        if cleaned and not any(cleaned.lower() in point.lower() for point in points):
            points.append(cleaned)
    return points[:5]


def _operational_checks(context: str, query: str) -> list[str]:
    haystack = f"{query} {context}".lower()
    checks = [
        "Verifica decorrenza, testo vigente e norme transitorie prima di citare il riferimento.",
        "Controlla se il fascicolo richiede aggiornamento di atti, scadenze, informative o procedure interne.",
    ]
    if "gazzetta ufficiale" in haystack or "entrata in vigore" in haystack:
        checks.append("Confronta data di pubblicazione ed entrata in vigore con gli adempimenti pendenti dello studio.")
    if "decreto legislativo" in haystack or "d.lgs" in haystack:
        checks.append("Verifica eventuali decreti attuativi, rinvii e coordinamento con la normativa previgente.")
    if "sanzion" in haystack or "obblig" in haystack:
        checks.append("Valuta impatti su obblighi, responsabilità e comunicazioni al cliente.")
    return checks[:5]


def _short(value: Any, limit: int) -> str:
    text = _normalize(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
