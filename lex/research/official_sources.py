from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    authority: str
    trust_class: str
    source_level: int
    source_kind: str


_CATALOG: dict[str, SourceDescriptor] = {
    "www.normattiva.it": SourceDescriptor("Normattiva", "A", 1, "normativa"),
    "normattiva.it": SourceDescriptor("Normattiva", "A", 1, "normativa"),
    "dati.normattiva.it": SourceDescriptor("dati.normattiva.it", "A", 1, "normativa"),
    "www.gazzettaufficiale.it": SourceDescriptor("Gazzetta Ufficiale", "A", 1, "normativa"),
    "gazzettaufficiale.it": SourceDescriptor("Gazzetta Ufficiale", "A", 1, "normativa"),
    "www.giustizia-amministrativa.it": SourceDescriptor("Giustizia Amministrativa", "A", 1, "giurisprudenza"),
    "giustizia-amministrativa.it": SourceDescriptor("Giustizia Amministrativa", "A", 1, "giurisprudenza"),
    "www.cortecostituzionale.it": SourceDescriptor("Corte costituzionale", "A", 1, "giurisprudenza"),
    "cortecostituzionale.it": SourceDescriptor("Corte costituzionale", "A", 1, "giurisprudenza"),
    "www.cortedicassazione.it": SourceDescriptor("Corte di cassazione", "A", 1, "giurisprudenza"),
    "cortedicassazione.it": SourceDescriptor("Corte di cassazione", "A", 1, "giurisprudenza"),
    "www.giustizia.it": SourceDescriptor("Ministero della Giustizia", "B", 2, "istituzionale"),
    "giustizia.it": SourceDescriptor("Ministero della Giustizia", "B", 2, "istituzionale"),
    "www.consiglionazionaleforense.it": SourceDescriptor("CNF", "B", 2, "istituzionale"),
    "consiglionazionaleforense.it": SourceDescriptor("CNF", "B", 2, "istituzionale"),
    "eur-lex.europa.eu": SourceDescriptor("EUR-Lex", "A", 1, "normativa"),
    "www.agenziaentrate.gov.it": SourceDescriptor("Agenzia delle Entrate", "B", 2, "istituzionale"),
    "agenziaentrate.gov.it": SourceDescriptor("Agenzia delle Entrate", "B", 2, "istituzionale"),
    "www.lavoro.gov.it": SourceDescriptor("Ministero del Lavoro", "B", 2, "istituzionale"),
    "lavoro.gov.it": SourceDescriptor("Ministero del Lavoro", "B", 2, "istituzionale"),
}


class OfficialSourcesCatalog:
    def _host(self, url: str) -> str:
        return (urlparse(str(url or "")).netloc or "").lower()

    def describe(self, url: str | None, authority: str | None = None) -> SourceDescriptor | None:
        host = self._host(url or "")
        if host in _CATALOG:
            return _CATALOG[host]
        normalized_authority = str(authority or "").strip().lower()
        if "official" in normalized_authority or "istituz" in normalized_authority:
            return SourceDescriptor(str(authority or "Fonte istituzionale"), "B", 2, "istituzionale")
        return None

    def enrich(self, row):
        data = dict(row or {})
        url = data.get("official_url") or data.get("url")
        descriptor = self.describe(url, data.get("authority"))
        if descriptor is None:
            return data
        data.setdefault("authority", descriptor.authority)
        data.setdefault("trust_class", descriptor.trust_class)
        data.setdefault("source_level", descriptor.source_level)
        data.setdefault("source_kind", descriptor.source_kind)
        data.setdefault("verified_reference", descriptor.source_level <= 2)
        data.setdefault("official_url", url)
        return data

    def extract(self, rows, citations):
        selected = []
        for item in list(rows or []):
            enriched = self.enrich(item)
            label = str(enriched.get("title") or enriched.get("source_id") or "Fonte ufficiale").strip()
            if int(enriched.get("source_level") or 0) <= 2 and label and label not in selected:
                selected.append(label)
        for citation in list(citations or []):
            url = getattr(citation, "url", None)
            authority = getattr(citation, "authority", None)
            descriptor = self.describe(url, authority)
            title = str(getattr(citation, "title", "") or "").strip()
            if descriptor is not None and title and title not in selected:
                selected.append(title)
        return selected[:12]

    def is_official(self, url: str | None, authority: str | None = None) -> bool:
        descriptor = self.describe(url, authority)
        return descriptor is not None and descriptor.source_level <= 2