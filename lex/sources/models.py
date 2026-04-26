from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SourceConfig:
    id: str
    name: str
    enabled: bool
    priority: int
    connector: str
    type: str = ""
    refresh: str = "manual"
    base_url: str = ""
    topics: list[str] = field(default_factory=list)
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentCandidate:
    source_id: str
    title: str
    url: str
    content: bytes | str | None = None
    content_type: str = ""
    filename: str = ""
    published_at: Optional[str] = None
    topics: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
