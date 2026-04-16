"""Deduplicazione delle evidenze di ricerca."""

from __future__ import annotations


class ResearchDeduplicator:
    def deduplicate(self, rows):
        seen = set()
        unique = []
        for row in list(rows or []):
            key = (
                str(row.get("source_type") or ""),
                str(row.get("source_id") or ""),
                str(row.get("title") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(dict(row))
        return unique