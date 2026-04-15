"""Deduplica delle evidenze Lex."""

from __future__ import annotations


def deduplicate_evidence(items):
    seen: set[tuple[str, str]] = set()
    deduped = []
    for item in list(items or []):
        key = (str(item.source_type), str(item.source_id))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
