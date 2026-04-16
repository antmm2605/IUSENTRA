"""Estrazione strutturata delle evidenze per Lex Research."""

from __future__ import annotations


class ResearchExtractor:
    def to_rows(self, items):
        rows = []
        for item in list(items or []):
            rows.append(
                {
                    "source_type": str(getattr(item, "source_type", "") or ""),
                    "source_id": str(getattr(item, "source_id", "") or ""),
                    "title": str(getattr(item, "title", "") or ""),
                    "content": str(getattr(item, "content", "") or ""),
                    "score": float(getattr(item, "score", 0.0) or 0.0),
                    "authority": str(getattr(item, "metadata", {}).get("authority") or ""),
                    "url": getattr(item, "metadata", {}).get("url"),
                    "metadata": dict(getattr(item, "metadata", {}) or {}),
                }
            )
        return rows