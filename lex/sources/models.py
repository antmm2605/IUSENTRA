from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional


def _stable_id(payload: dict[str, Any]) -> str:
    # Helper locale (6 righe) per non accoppiare lex.sources a lex.learning:
    # stessa semantica di lex.learning.models.stable_id_from.
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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


@dataclass
class SourceCandidate:
    """Risultato di una RICERCA governata (hit di discovery), distinto da
    `DocumentCandidate` che è un documento già individuato da un connettore
    di ingestion. Il campo `content` inline serve alla modalità offline/test
    (StaticSearchProvider): il reader lo usa senza toccare la rete."""

    url: str
    title: str = ""
    snippet: str = ""
    source_id: str = ""
    discovered_by: str = ""
    query: str = ""
    confidence: float = 0.0
    content: str = ""
    content_type: str = "text/plain"

    def stable_id(self) -> str:
        return _stable_id({"url": self.url.casefold()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "source_id": self.source_id,
            "discovered_by": self.discovered_by,
            "query": self.query,
            "confidence": round(float(self.confidence), 3),
            "content_type": self.content_type,
            "has_inline_content": bool(self.content),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SourceCandidate:
        return cls(
            url=str(payload.get("url") or "").strip(),
            title=str(payload.get("title") or "").strip(),
            snippet=str(payload.get("snippet") or "").strip(),
            source_id=str(payload.get("source_id") or "").strip(),
            discovered_by=str(payload.get("discovered_by") or "").strip(),
            query=str(payload.get("query") or "").strip(),
            confidence=float(payload.get("confidence") or 0.0),
            content=str(payload.get("content") or ""),
            content_type=str(payload.get("content_type") or "text/plain").strip(),
        )


@dataclass
class SourceFetchResult:
    """Esito del fetch cortese di una URL pubblica (PoliteFetcher)."""

    url: str
    status: str  # ok | robots_blocked | http_error | too_large | invalid_url | network_error
    final_url: str = ""
    http_status: int = 0
    content_type: str = ""
    content: bytes | None = None
    fetched_at: str = ""
    elapsed_ms: int = 0
    warnings: list[str] = field(default_factory=list)

    def stable_id(self) -> str:
        return _stable_id({"url": self.url.casefold(), "fetched_at": self.fetched_at})

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "final_url": self.final_url,
            "http_status": int(self.http_status),
            "content_type": self.content_type,
            "content_bytes": len(self.content) if self.content else 0,
            "fetched_at": self.fetched_at,
            "elapsed_ms": int(self.elapsed_ms),
            "warnings": list(self.warnings),
        }


@dataclass
class SourceTrustAssessment:
    """Valutazione di affidabilità di una fonte per l'apprendimento di Lex.

    Composta da `lex.research.source_policy` (tier/score/affidabilità per area)
    e dal registro fonti governato; `allowed_for_learning` è la decisione
    fail-closed finale (denylist e credenziali vincono sempre)."""

    url: str
    domain: str = ""
    area: str = ""
    tier: str = "unknown"
    score: float = 0.0
    reliability: str = "low"
    authority_band: str = ""
    official: bool = False
    source_id: str = ""
    requires_credentials: bool = False
    allowed_for_learning: bool = False
    requires_review: bool = False
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def stable_id(self) -> str:
        return _stable_id({"url": self.url.casefold(), "area": self.area})

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "domain": self.domain,
            "area": self.area,
            "tier": self.tier,
            "score": round(float(self.score), 3),
            "reliability": self.reliability,
            "authority_band": self.authority_band,
            "official": bool(self.official),
            "source_id": self.source_id,
            "requires_credentials": bool(self.requires_credentials),
            "allowed_for_learning": bool(self.allowed_for_learning),
            "requires_review": bool(self.requires_review),
            "reasons": list(self.reasons),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SourceTrustAssessment:
        return cls(
            url=str(payload.get("url") or "").strip(),
            domain=str(payload.get("domain") or "").strip(),
            area=str(payload.get("area") or "").strip(),
            tier=str(payload.get("tier") or "unknown").strip(),
            score=float(payload.get("score") or 0.0),
            reliability=str(payload.get("reliability") or "low").strip(),
            authority_band=str(payload.get("authority_band") or "").strip(),
            official=bool(payload.get("official")),
            source_id=str(payload.get("source_id") or "").strip(),
            requires_credentials=bool(payload.get("requires_credentials")),
            allowed_for_learning=bool(payload.get("allowed_for_learning")),
            requires_review=bool(payload.get("requires_review")),
            reasons=[str(item) for item in payload.get("reasons") or [] if str(item).strip()],
            warnings=[str(item) for item in payload.get("warnings") or [] if str(item).strip()],
        )
