"""Riconoscimento delle fonti affidabili del pacchetto di ricerca Lex."""

from __future__ import annotations


_TRUSTED_TYPES = {
    "normativa",
    "giurisprudenza",
    "legal_intelligence",
    "fascicolo",
    "documento",
    "telematico",
    "web_ufficiale",
}


class TrustedSourcesCatalog:
    def extract(self, rows, citations):
        selected = []
        for item in list(rows or []):
            source_type = str(item.get("source_type") or "").lower()
            label = str(item.get("title") or item.get("source_id") or source_type or "Fonte").strip()
            if source_type in _TRUSTED_TYPES and label and label not in selected:
                selected.append(label)
        for citation in list(citations or []):
            source_type = str(getattr(citation, "source_type", "") or "").lower()
            title = str(getattr(citation, "title", "") or "").strip()
            if source_type in _TRUSTED_TYPES and title and title not in selected:
                selected.append(title)
        return selected[:12]