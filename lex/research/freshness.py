"""Metriche semplici di freschezza per l'evidence pack Lex."""

from __future__ import annotations


class FreshnessAnalyzer:
    def measure(self, rows):
        dated_rows = []
        for row in list(rows or []):
            metadata = dict(row.get("metadata") or {})
            value = metadata.get("data") or metadata.get("date") or metadata.get("updated_at")
            if value:
                dated_rows.append(str(value))
        latest = max(dated_rows) if dated_rows else ""
        return {
            "dated_items": len(dated_rows),
            "latest_date": latest,
        }