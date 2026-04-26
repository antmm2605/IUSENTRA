"""Snippet HTML sicuri per i risultati della Ricerca Studio."""

from __future__ import annotations

import html
import re

from .normalizer import clean_text


def make_snippet(text: str, query: str, *, max_chars: int = 220) -> str:
    source = clean_text(text)
    if not source:
        return ""
    words = [w for w in re.split(r"\s+", clean_text(query)) if len(w) >= 2]
    lower = source.lower()
    start = 0
    for word in words:
        pos = lower.find(word.lower())
        if pos >= 0:
            start = max(0, pos - 70)
            break
    chunk = source[start : start + max_chars]
    if start > 0:
        chunk = "..." + chunk
    if start + max_chars < len(source):
        chunk += "..."
    escaped = html.escape(chunk)
    for word in sorted(set(words), key=len, reverse=True):
        escaped = re.sub(
            re.escape(html.escape(word)),
            lambda m: f"<mark>{m.group(0)}</mark>",
            escaped,
            flags=re.IGNORECASE,
        )
    return escaped
