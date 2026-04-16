"""Classificazione delle evidenze per Lex Research."""

from __future__ import annotations


class ResearchClassifier:
    def classify(self, rows):
        classified = []
        for row in list(rows or []):
            item = dict(row)
            source_type = str(item.get("source_type") or "").lower()
            if source_type == "web_ufficiale":
                bucket = "official"
            elif source_type in {"normativa", "giurisprudenza", "legal_intelligence", "telematico"}:
                bucket = "trusted"
            else:
                bucket = "internal"
            item["bucket"] = bucket
            classified.append(item)
        return classified