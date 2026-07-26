"""Normalizzazione sicura dei testi della Ricerca Studio."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Any

SECRET_MARKERS = (
    "password",
    "token",
    "api_key",
    "apikey",
    "secret",
    "pin",
    "private_key",
    "chiave privata",
)


class _PlainTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data:
            self.parts.append(data)


def _html_to_text(value: str) -> str:
    parser = _PlainTextHTMLParser()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        return value
    return " ".join(parser.parts) if parser.parts else value


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value)
    if "<" in text and ">" in text:
        text = _html_to_text(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_search_text(value: Any) -> str:
    text = clean_text(value).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^\w@./+-]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def normalize_identifier(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", clean_text(value)).upper()


def looks_sensitive_key(key: str) -> bool:
    lowered = (key or "").lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def safe_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if looks_sensitive_key(str(key)):
            continue
        if isinstance(value, dict):
            result[str(key)] = safe_metadata(value)
        elif isinstance(value, list):
            cleaned = []
            for item in value[:20]:
                cleaned.append(safe_metadata(item) if isinstance(item, dict) else clean_text(item))
            result[str(key)] = cleaned
        else:
            result[str(key)] = clean_text(value)
    return result


def italian_date(value: Any) -> str:
    text = clean_text(value)
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text
