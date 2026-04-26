"""Modelli dati per la Ricerca Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class GlobalSearchDocument:
    tenant_id: str
    entity_type: str
    entity_id: str
    title: str
    subtitle: str = ""
    body: str = ""
    keywords: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    client_id: str = ""
    fascicolo_id: str = ""
    pratica_id: str = ""
    source_module: str = ""
    source_url: str = ""
    visibility: str = "studio"
    permission_scope: str = "studio"
    created_at: str = ""
    updated_at: str = ""

    @property
    def search_text(self) -> str:
        return " ".join(
            part.strip()
            for part in (self.title, self.subtitle, self.body, self.keywords)
            if isinstance(part, str) and part.strip()
        )


@dataclass(slots=True)
class GlobalSearchResult:
    id: int
    tenant_id: str
    entity_type: str
    entity_id: str
    title: str
    subtitle: str
    snippet: str
    score: float
    source_module: str
    source_url: str
    client_id: str = ""
    fascicolo_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "title": self.title,
            "titolo": self.title,
            "subtitle": self.subtitle,
            "sottotitolo": self.subtitle,
            "snippet": self.snippet,
            "score": round(float(self.score or 0), 4),
            "source_module": self.source_module,
            "source_url": self.source_url,
            "url": self.source_url,
            "client_id": self.client_id,
            "fascicolo_id": self.fascicolo_id,
            "metadata": self.metadata,
            "badges": self.metadata.get("badges", []),
            "actions": self.metadata.get("actions", []),
            "icon": self.metadata.get("icon", "bi-search"),
            "icona": self.metadata.get("icon", "bi-search"),
            "date": self.metadata.get("date", ""),
        }
