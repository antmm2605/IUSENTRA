"""Normalizzazione testo per confronto e indicizzazione."""

from __future__ import annotations

import re
from html import unescape


TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")


def normalize_text(content: bytes | str, content_type: str = "") -> str:
    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="ignore")
    else:
        text = str(content or "")
    if "html" in (content_type or "").lower() or "<html" in text.lower():
        text = TAG_RE.sub(" ", text)
    text = unescape(text)
    return SPACE_RE.sub(" ", text).strip()
