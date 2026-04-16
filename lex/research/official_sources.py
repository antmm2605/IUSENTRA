"""Riconoscimento fonti ufficiali nel pacchetto di ricerca Lex."""

from __future__ import annotations


_OFFICIAL_HOST_TOKENS = (
    "giustizia.it",
    "normattiva.it",
    "gazzettaufficiale.it",
    "giustizia-amministrativa.it",
    "consiglionazionaleforense.it",
    "agenziaentrate.gov.it",
)


class OfficialSourcesCatalog:
    def extract(self, rows, citations):
        selected = []
        for item in list(rows or []):
            url = str(item.get("url") or "").lower()
            authority = str(item.get("authority") or "").lower()
            source_type = str(item.get("source_type") or "").lower()
            label = str(item.get("title") or item.get("source_id") or "Fonte ufficiale").strip()
            if source_type == "web_ufficiale" or "official" in authority or any(token in url for token in _OFFICIAL_HOST_TOKENS):
                if label and label not in selected:
                    selected.append(label)
        for citation in list(citations or []):
            url = str(getattr(citation, "url", "") or "").lower()
            title = str(getattr(citation, "title", "") or "").strip()
            if title and any(token in url for token in _OFFICIAL_HOST_TOKENS) and title not in selected:
                selected.append(title)
        return selected[:8]