from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml


_REGISTRY_PATH = Path(__file__).resolve().parent / "source_policy" / "sources_registry.yaml"

_STATUS_LABELS: dict[str, str] = {
    "open_api": "API aperta",
    "open_data": "Open data",
    "open_ckan": "Catalogo open data",
    "open_data_plus_api": "Open data con API",
    "open_sparql": "Endpoint SPARQL aperto",
    "open_sparql_plus_download": "SPARQL e download aperto",
    "rss_export": "Feed ufficiale",
    "open_plus_registration": "Registrazione richiesta",
    "portal_data": "Portale dati",
    "portal_only": "Consultazione da portale",
    "portal_only_regulated": "Portale regolamentato",
    "portal_or_institutional_channel": "Portale o canale istituzionale",
    "partner_api": "Fonte partner con credenziali",
    "partner_or_reserved": "Fonte partner o riservata",
    "reserved_portal": "Portale riservato",
}

_PUBLIC_WEB_STATUSES = {
    "open_api",
    "open_data",
    "open_ckan",
    "open_data_plus_api",
    "open_sparql",
    "open_sparql_plus_download",
    "rss_export",
    "open_plus_registration",
    "portal_data",
}

_REGISTRATION_STATUSES = {"open_plus_registration"}
_PARTNER_STATUSES = {"partner_api"}
_RESTRICTED_STATUSES = {
    "portal_only",
    "portal_only_regulated",
    "portal_or_institutional_channel",
    "partner_api",
    "partner_or_reserved",
    "reserved_portal",
}

_ALIASES: dict[str, str] = {
    "gazzetta_ufficiale": "gazzetta_rss",
    "eur_lex": "eurlex",
    "merito_civile_bdp": "bdp_giustizia",
    "registro_imprese": "registro_imprese_api",
    "pst_reginde": "pst_reginde_pda",
}


def _clean_spaces(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_text(value: Any) -> str:
    return _clean_spaces(value).lower()


def _normalize_domain(value: Any) -> str:
    text = _clean_spaces(value).lower()
    if not text:
        return ""
    if "://" in text:
        text = urlparse(text).netloc or text
    if text.startswith("www."):
        text = text[4:]
    if ":" in text:
        text = text.split(":", 1)[0]
    return text.strip(".")


def _status_label(status: str) -> str:
    normalized = _normalize_text(status)
    return _STATUS_LABELS.get(normalized, "Fonte governata")


def _entrypoint_values(entrypoints: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for value in dict(entrypoints or {}).values():
        clean = _clean_spaces(value)
        if clean:
            values.append(clean)
    return values


@dataclass(frozen=True, slots=True)
class RegisteredSource:
    key: str
    label: str
    category: str
    status: str
    priority: str
    official: bool
    base_url: str
    entrypoints: dict[str, str]
    formats: list[str]
    auth: str
    use_cases: list[str]

    @property
    def access_label(self) -> str:
        return _status_label(self.status)

    @property
    def supports_public_web_search(self) -> bool:
        return _normalize_text(self.status) in _PUBLIC_WEB_STATUSES

    @property
    def requires_registration(self) -> bool:
        return _normalize_text(self.status) in _REGISTRATION_STATUSES

    @property
    def is_partner_source(self) -> bool:
        return _normalize_text(self.status) in _PARTNER_STATUSES

    @property
    def is_restricted_source(self) -> bool:
        return _normalize_text(self.status) in _RESTRICTED_STATUSES

    @property
    def requires_credentials(self) -> bool:
        auth_value = _normalize_text(self.auth)
        if auth_value in {"", "none", "nessuna", "nessuno"}:
            return self.is_partner_source or self.requires_registration
        if "none" in auth_value or "nessuna" in auth_value:
            return self.is_partner_source or self.requires_registration
        return True

    @property
    def source_kind(self) -> str:
        category = _normalize_text(self.category)
        label = _normalize_text(self.label)
        if "normativa" in category or "gazzetta" in label or "normattiva" in label or "eur-lex" in label:
            return "normativa"
        if "giurisprudenza" in category or "corte" in label or "cassazione" in label:
            return "giurisprudenza"
        if "processo" in category or "telematico" in category or "pat" in label or "ptt" in label:
            return "telematico"
        return "istituzionale"

    @property
    def trust_class(self) -> str:
        return "A" if self.official else "B"

    @property
    def source_level(self) -> int:
        return 1 if self.official else 2

    @property
    def authority_band(self) -> str:
        if self.is_restricted_source:
            return "istituzionale_riservata"
        if self.is_partner_source:
            return "partner_istituzionale"
        if self.official:
            return "istituzionale_o_primaria"
        return "professionale_affidabile"

    @property
    def domains(self) -> tuple[str, ...]:
        values = [self.base_url, *_entrypoint_values(self.entrypoints)]
        rows: list[str] = []
        seen: set[str] = set()
        for value in values:
            domain = _normalize_domain(value)
            if not domain or domain in seen:
                continue
            seen.add(domain)
            rows.append(domain)
        return tuple(rows)

    def search_haystack(self) -> str:
        parts = [
            self.key,
            self.label,
            self.category,
            self.status,
            self.priority,
            self.auth,
            " ".join(self.formats),
            " ".join(self.use_cases),
            " ".join(_entrypoint_values(self.entrypoints)),
        ]
        return _normalize_text(" ".join(parts))

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "status": self.status,
            "access_label": self.access_label,
            "priority": self.priority,
            "official": self.official,
            "base_url": self.base_url,
            "auth": self.auth,
            "formats": list(self.formats),
            "use_cases": list(self.use_cases),
            "requires_credentials": self.requires_credentials,
            "restricted": self.is_restricted_source,
            "partner": self.is_partner_source,
            "supports_public_web_search": self.supports_public_web_search,
            "requires_registration": self.requires_registration,
        }


class SourceRegistry:
    def __init__(self, sources: list[RegisteredSource]) -> None:
        self._sources = list(sources)
        self._by_key: dict[str, RegisteredSource] = {}
        self._by_domain: dict[str, list[RegisteredSource]] = {}
        for source in self._sources:
            self._by_key[source.key] = source
            for domain in source.domains:
                self._by_domain.setdefault(domain, []).append(source)
        for alias, target in _ALIASES.items():
            if alias not in self._by_key and target in self._by_key:
                self._by_key[alias] = self._by_key[target]

    @classmethod
    def load(cls, path: Path | None = None) -> "SourceRegistry":
        registry_path = path or _REGISTRY_PATH
        with registry_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        raw_sources = list(payload.get("sources") or [])
        sources: list[RegisteredSource] = []
        for raw in raw_sources:
            row = dict(raw or {})
            sources.append(
                RegisteredSource(
                    key=_clean_spaces(row.get("key")),
                    label=_clean_spaces(row.get("label")),
                    category=_clean_spaces(row.get("category")),
                    status=_clean_spaces(row.get("status")),
                    priority=_clean_spaces(row.get("priority")),
                    official=bool(row.get("official")),
                    base_url=_clean_spaces(row.get("base_url")),
                    entrypoints={str(key): _clean_spaces(value) for key, value in dict(row.get("entrypoints") or {}).items()},
                    formats=[_clean_spaces(item) for item in list(row.get("formats") or []) if _clean_spaces(item)],
                    auth=_clean_spaces(row.get("auth")),
                    use_cases=[_clean_spaces(item) for item in list(row.get("use_cases") or []) if _clean_spaces(item)],
                )
            )
        return cls(sources)

    def all(self) -> list[RegisteredSource]:
        return list(self._sources)

    def get(self, key: str | None) -> RegisteredSource | None:
        normalized = _normalize_text(key)
        if not normalized:
            return None
        return self._by_key.get(normalized)

    def find_by_host(self, value: str | None) -> RegisteredSource | None:
        domain = _normalize_domain(value)
        if not domain:
            return None
        exact = self._by_domain.get(domain)
        if exact:
            return self._best_match(exact)
        candidates: list[RegisteredSource] = []
        for candidate_domain, sources in self._by_domain.items():
            if domain == candidate_domain or domain.endswith("." + candidate_domain):
                candidates.extend(sources)
        return self._best_match(candidates)

    def search(self, query: str, *, limit: int = 6) -> list[RegisteredSource]:
        normalized = _normalize_text(query)
        if not normalized:
            return []
        tokens = [token for token in normalized.split(" ") if len(token) >= 3]
        ranked: list[tuple[int, RegisteredSource]] = []
        for source in self._sources:
            haystack = source.search_haystack()
            score = 0
            for token in tokens:
                if token in haystack:
                    score += 2
            if normalized in haystack:
                score += 4
            if score <= 0:
                continue
            if source.priority == "P0":
                score += 2
            if source.official:
                score += 1
            ranked.append((score, source))
        ranked.sort(key=lambda item: (-item[0], item[1].priority, item[1].label))
        return [item[1] for item in ranked[:limit]]

    def resolve_requested_sources(
        self,
        query: str,
        *,
        explicit_source_ids: list[str] | None = None,
        limit: int = 6,
    ) -> list[RegisteredSource]:
        selected: list[RegisteredSource] = []
        seen: set[str] = set()

        def _push(source: RegisteredSource | None) -> None:
            if source is None or source.key in seen:
                return
            seen.add(source.key)
            selected.append(source)

        for source_id in list(explicit_source_ids or []):
            _push(self.get(source_id))
            if len(selected) >= limit:
                return selected[:limit]

        for source in self.search(query, limit=limit):
            _push(source)
            if len(selected) >= limit:
                return selected[:limit]
        return selected[:limit]

    def public_web_domains(self, source_keys: list[str]) -> list[str]:
        rows: list[str] = []
        seen: set[str] = set()
        for source_key in list(source_keys or []):
            source = self.get(source_key)
            if source is None or not source.supports_public_web_search:
                continue
            for domain in source.domains:
                if not domain or domain in seen:
                    continue
                seen.add(domain)
                rows.append(domain)
        return rows

    def _best_match(self, rows: list[RegisteredSource]) -> RegisteredSource | None:
        if not rows:
            return None
        ordered = sorted(
            rows,
            key=lambda source: (
                source.is_restricted_source,
                source.is_partner_source,
                source.priority != "P0",
                source.label,
            ),
        )
        return ordered[0]


@lru_cache(maxsize=1)
def get_source_registry() -> SourceRegistry:
    return SourceRegistry.load()


__all__ = ["RegisteredSource", "SourceRegistry", "get_source_registry"]
