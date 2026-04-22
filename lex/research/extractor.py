"""Estrazione strutturata delle evidenze per Lex Research."""

from __future__ import annotations


class ResearchExtractor:
    def to_rows(self, items):
        rows = []
        for item in list(items or []):
            metadata = dict(getattr(item, "metadata", {}) or {})
            rows.append(
                {
                    "source_type": str(getattr(item, "source_type", "") or ""),
                    "source_id": str(getattr(item, "source_id", "") or ""),
                    "title": str(getattr(item, "title", "") or ""),
                    "content": str(getattr(item, "content", "") or ""),
                    "score": float(getattr(item, "score", 0.0) or 0.0),
                    "authority": str(getattr(item, "authority", "") or metadata.get("authority") or ""),
                    "url": getattr(item, "official_url", None) or metadata.get("official_url") or metadata.get("url"),
                    "official_url": getattr(item, "official_url", None) or metadata.get("official_url"),
                    "trust_class": str(getattr(item, "trust_class", "") or metadata.get("trust_class") or ""),
                    "source_level": int(getattr(item, "source_level", 0) or metadata.get("source_level") or 0),
                    "verified_reference": bool(getattr(item, "verified_reference", False) or metadata.get("verified_reference")),
                    "published_at": getattr(item, "published_at", None) or metadata.get("published_at"),
                    "metadata": metadata,
                }
            )
        return rows
