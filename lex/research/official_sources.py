from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from .source_registry import RegisteredSource, get_source_registry


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    authority: str
    trust_class: str
    source_level: int
    source_kind: str
    registry_key: str = ""
    access_status: str = ""
    access_label: str = ""
    category: str = ""
    priority: str = ""
    auth_mode: str = ""
    official: bool = False
    requires_credentials: bool = False
    restricted: bool = False
    supports_web_search: bool = False
    auto_verified_reference: bool = True


_LEGACY_CATALOG: dict[str, SourceDescriptor] = {
    "www.normattiva.it": SourceDescriptor("Normattiva", "A", 1, "normativa", official=True),
    "normattiva.it": SourceDescriptor("Normattiva", "A", 1, "normativa", official=True),
    "dati.normattiva.it": SourceDescriptor("dati.normattiva.it", "A", 1, "normativa", official=True),
    "www.gazzettaufficiale.it": SourceDescriptor("Gazzetta Ufficiale", "A", 1, "normativa", official=True),
    "gazzettaufficiale.it": SourceDescriptor("Gazzetta Ufficiale", "A", 1, "normativa", official=True),
    "www.giustizia-amministrativa.it": SourceDescriptor("Giustizia Amministrativa", "A", 1, "giurisprudenza", official=True),
    "giustizia-amministrativa.it": SourceDescriptor("Giustizia Amministrativa", "A", 1, "giurisprudenza", official=True),
    "www.cortecostituzionale.it": SourceDescriptor("Corte costituzionale", "A", 1, "giurisprudenza", official=True),
    "cortecostituzionale.it": SourceDescriptor("Corte costituzionale", "A", 1, "giurisprudenza", official=True),
    "www.cortedicassazione.it": SourceDescriptor("Corte di cassazione", "A", 1, "giurisprudenza", official=True),
    "cortedicassazione.it": SourceDescriptor("Corte di cassazione", "A", 1, "giurisprudenza", official=True),
    "www.giustizia.it": SourceDescriptor("Ministero della Giustizia", "B", 2, "istituzionale", official=True),
    "giustizia.it": SourceDescriptor("Ministero della Giustizia", "B", 2, "istituzionale", official=True),
    "www.consiglionazionaleforense.it": SourceDescriptor("CNF", "B", 2, "istituzionale", official=True),
    "consiglionazionaleforense.it": SourceDescriptor("CNF", "B", 2, "istituzionale", official=True),
    "eur-lex.europa.eu": SourceDescriptor("EUR-Lex", "A", 1, "normativa", official=True),
    "www.agenziaentrate.gov.it": SourceDescriptor("Agenzia delle Entrate", "B", 2, "istituzionale", official=True),
    "agenziaentrate.gov.it": SourceDescriptor("Agenzia delle Entrate", "B", 2, "istituzionale", official=True),
    "www.lavoro.gov.it": SourceDescriptor("Ministero del Lavoro", "B", 2, "istituzionale", official=True),
    "lavoro.gov.it": SourceDescriptor("Ministero del Lavoro", "B", 2, "istituzionale", official=True),
}


def _clean_spaces(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _source_from_registry(source: RegisteredSource) -> SourceDescriptor:
    auto_verified = not (source.is_restricted_source or source.is_partner_source or source.requires_registration)
    return SourceDescriptor(
        authority=source.label or source.key,
        trust_class=source.trust_class,
        source_level=source.source_level,
        source_kind=source.source_kind,
        registry_key=source.key,
        access_status=source.status,
        access_label=source.access_label,
        category=source.category,
        priority=source.priority,
        auth_mode=source.auth,
        official=source.official,
        requires_credentials=source.requires_credentials,
        restricted=source.is_restricted_source,
        supports_web_search=source.supports_public_web_search,
        auto_verified_reference=auto_verified,
    )


class OfficialSourcesCatalog:
    def __init__(self) -> None:
        self.registry = get_source_registry()

    def _host(self, url: str) -> str:
        return (urlparse(str(url or "")).netloc or "").lower()

    def describe(self, url: str | None, authority: str | None = None, source_id: str | None = None) -> SourceDescriptor | None:
        registry_match = self.registry.get(source_id) if source_id else None
        if registry_match is None:
            registry_match = self.registry.find_by_host(url or "")
        if registry_match is not None:
            return _source_from_registry(registry_match)

        host = self._host(url or "")
        if host in _LEGACY_CATALOG:
            return _LEGACY_CATALOG[host]

        normalized_authority = _clean_spaces(authority).lower()
        if "official" in normalized_authority or "istituz" in normalized_authority:
            return SourceDescriptor(str(authority or "Fonte istituzionale"), "B", 2, "istituzionale", official=True)
        return None

    def enrich(self, row):
        data = dict(row or {})
        metadata = dict(data.get("metadata") or {})
        url = data.get("official_url") or data.get("url") or metadata.get("official_url") or metadata.get("url")
        source_id = data.get("source_id") or metadata.get("source_id") or metadata.get("official_source_id")
        descriptor = self.describe(url, data.get("authority") or metadata.get("authority"), source_id)
        if descriptor is None:
            data["metadata"] = metadata
            return data

        data.setdefault("authority", descriptor.authority)
        data.setdefault("trust_class", descriptor.trust_class)
        data.setdefault("source_level", descriptor.source_level)
        data.setdefault("source_kind", descriptor.source_kind)
        if descriptor.auto_verified_reference:
            data.setdefault("verified_reference", descriptor.source_level <= 2)
        data.setdefault("official_url", url)
        data.setdefault("source_registry_key", descriptor.registry_key)
        data.setdefault("source_access_status", descriptor.access_status)
        data.setdefault("source_access_label", descriptor.access_label)
        data.setdefault("source_category", descriptor.category)
        data.setdefault("source_priority", descriptor.priority)
        data.setdefault("source_auth_mode", descriptor.auth_mode)
        data.setdefault("source_official", descriptor.official)
        data.setdefault("source_requires_credentials", descriptor.requires_credentials)
        data.setdefault("source_restricted", descriptor.restricted)
        data.setdefault("source_supports_web_search", descriptor.supports_web_search)

        metadata.setdefault("authority", data.get("authority"))
        metadata.setdefault("trust_class", data.get("trust_class"))
        metadata.setdefault("source_level", data.get("source_level"))
        metadata.setdefault("verified_reference", bool(data.get("verified_reference")))
        metadata.setdefault("official_url", data.get("official_url"))
        if descriptor.registry_key:
            metadata.setdefault("source_registry_key", descriptor.registry_key)
            metadata.setdefault("source_access_status", descriptor.access_status)
            metadata.setdefault("source_access_label", descriptor.access_label)
            metadata.setdefault("source_category", descriptor.category)
            metadata.setdefault("source_priority", descriptor.priority)
            metadata.setdefault("source_auth_mode", descriptor.auth_mode)
            metadata.setdefault("source_official", descriptor.official)
            metadata.setdefault("source_requires_credentials", descriptor.requires_credentials)
            metadata.setdefault("source_restricted", descriptor.restricted)
            metadata.setdefault("source_supports_web_search", descriptor.supports_web_search)
        data["metadata"] = metadata
        return data

    def extract(self, rows, citations):
        selected = []
        for item in list(rows or []):
            enriched = self.enrich(item)
            label = str(enriched.get("title") or enriched.get("authority") or enriched.get("source_id") or "Fonte ufficiale").strip()
            if int(enriched.get("source_level") or 0) <= 2 and label and label not in selected:
                selected.append(label)
        for citation in list(citations or []):
            url = getattr(citation, "url", None)
            authority = getattr(citation, "authority", None)
            source_id = getattr(citation, "source_id", None)
            descriptor = self.describe(url, authority, source_id)
            title = str(getattr(citation, "title", "") or "").strip()
            if descriptor is not None and title and title not in selected:
                selected.append(title)
        return selected[:12]

    def is_official(self, url: str | None, authority: str | None = None, source_id: str | None = None) -> bool:
        descriptor = self.describe(url, authority, source_id)
        return descriptor is not None and descriptor.source_level <= 2


__all__ = ["OfficialSourcesCatalog", "SourceDescriptor"]
