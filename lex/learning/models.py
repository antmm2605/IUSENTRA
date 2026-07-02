"""Modelli serializzabili del dominio di apprendimento di Lex.

Ogni modello ha `to_dict`/`from_dict` e uno `stable_id()` deterministico
(sha256 del JSON canonico dei soli campi identitari, primi 16 esadecimali):
è la chiave di dedup della memoria JSONL (`lex.knowledge.knowledge_base`).
Nessuna dipendenza pesante: solo stdlib.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def stable_id_from(payload: dict[str, Any]) -> str:
    """Identificativo deterministico e ordinamento-indipendente di un payload."""

    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


@dataclass(slots=True)
class LegalCitation:
    """Riferimento giuridico estratto da un testo (norma, sentenza, atto UE...)."""

    raw_text: str
    normalized_text: str
    reference_type: str
    confidence: float = 0.0
    start: int = -1
    end: int = -1
    snippet: str = ""
    source_url: str = ""
    official_url: str = ""

    def stable_id(self) -> str:
        return stable_id_from({"type": self.reference_type, "normalized": self.normalized_text.casefold()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
            "reference_type": self.reference_type,
            "confidence": round(float(self.confidence), 2),
            "start": int(self.start),
            "end": int(self.end),
            "snippet": self.snippet,
            "source_url": self.source_url,
            "official_url": self.official_url,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LegalCitation:
        return cls(
            raw_text=_clean(payload.get("raw_text")),
            normalized_text=_clean(payload.get("normalized_text")),
            reference_type=_clean(payload.get("reference_type")),
            confidence=float(payload.get("confidence") or 0.0),
            start=int(payload.get("start", -1)),
            end=int(payload.get("end", -1)),
            snippet=_clean(payload.get("snippet")),
            source_url=_clean(payload.get("source_url")),
            official_url=_clean(payload.get("official_url")),
        )


@dataclass(slots=True)
class LegalTermObservation:
    """Osservazione di un termine giuridico in un testo (noto o candidato)."""

    normalized: str
    label: str
    kind: str  # concetto | correlato | candidato
    area: str = ""
    occurrences: int = 0
    confidence: float = 0.0
    contexts: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)

    def stable_id(self) -> str:
        return stable_id_from({"normalized": self.normalized.casefold(), "area": self.area})

    def to_dict(self) -> dict[str, Any]:
        return {
            "normalized": self.normalized,
            "label": self.label,
            "kind": self.kind,
            "area": self.area,
            "occurrences": int(self.occurrences),
            "confidence": round(float(self.confidence), 2),
            "contexts": list(self.contexts),
            "source_ids": list(self.source_ids),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LegalTermObservation:
        return cls(
            normalized=_clean(payload.get("normalized")),
            label=_clean(payload.get("label")),
            kind=_clean(payload.get("kind")) or "candidato",
            area=_clean(payload.get("area")),
            occurrences=int(payload.get("occurrences") or 0),
            confidence=float(payload.get("confidence") or 0.0),
            contexts=[_clean(item) for item in payload.get("contexts") or [] if _clean(item)],
            source_ids=[_clean(item) for item in payload.get("source_ids") or [] if _clean(item)],
        )


@dataclass(slots=True)
class LegalSourceSample:
    """Campione testuale di partenza (locale, senza PII) da cui Lex impara."""

    sample_id: str
    title: str
    text: str
    area: str = ""
    url: str = ""
    authority: str = ""
    source_type: str = "sample"
    fetched_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def stable_id(self) -> str:
        return stable_id_from({"sample_id": self.sample_id or self.url or self.title.casefold()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "title": self.title,
            "text": self.text,
            "area": self.area,
            "url": self.url,
            "authority": self.authority,
            "source_type": self.source_type,
            "fetched_at": self.fetched_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LegalSourceSample:
        return cls(
            sample_id=_clean(payload.get("sample_id")),
            title=_clean(payload.get("title")),
            text=str(payload.get("text") or ""),
            area=_clean(payload.get("area")),
            url=_clean(payload.get("url")),
            authority=_clean(payload.get("authority")),
            source_type=_clean(payload.get("source_type")) or "sample",
            fetched_at=_clean(payload.get("fetched_at")),
            metadata=dict(payload.get("metadata") or {}),
        )


@dataclass(slots=True)
class LegalLanguageProfile:
    """Profilo linguistico-giuridico deterministico di un testo."""

    sample_id: str
    area: str
    characters: int
    tokens: int
    sentence_count: int
    average_sentence_length: float
    legal_density: float
    complexity_index: float
    citations: list[LegalCitation] = field(default_factory=list)
    terms: list[LegalTermObservation] = field(default_factory=list)

    def stable_id(self) -> str:
        return stable_id_from({"sample_id": self.sample_id, "characters": self.characters, "tokens": self.tokens})

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "area": self.area,
            "characters": int(self.characters),
            "tokens": int(self.tokens),
            "sentence_count": int(self.sentence_count),
            "average_sentence_length": round(float(self.average_sentence_length), 2),
            "legal_density": round(float(self.legal_density), 4),
            "complexity_index": round(float(self.complexity_index), 3),
            "citations": [item.to_dict() for item in self.citations],
            "terms": [item.to_dict() for item in self.terms],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LegalLanguageProfile:
        return cls(
            sample_id=_clean(payload.get("sample_id")),
            area=_clean(payload.get("area")),
            characters=int(payload.get("characters") or 0),
            tokens=int(payload.get("tokens") or 0),
            sentence_count=int(payload.get("sentence_count") or 0),
            average_sentence_length=float(payload.get("average_sentence_length") or 0.0),
            legal_density=float(payload.get("legal_density") or 0.0),
            complexity_index=float(payload.get("complexity_index") or 0.0),
            citations=[LegalCitation.from_dict(item) for item in payload.get("citations") or []],
            terms=[LegalTermObservation.from_dict(item) for item in payload.get("terms") or []],
        )


@dataclass(slots=True)
class SourceReadingResult:
    """Esito della lettura governata di una fonte (offline o web)."""

    url: str
    title: str = ""
    area: str = ""
    status: str = "ok"  # ok | robots_blocked | http_error | too_large | invalid_url | network_error | empty_text
    source_id: str = ""
    text_characters: int = 0
    citations_normalized: list[str] = field(default_factory=list)
    terms_normalized: list[str] = field(default_factory=list)
    trust: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = ""
    warnings: list[str] = field(default_factory=list)

    def stable_id(self) -> str:
        return stable_id_from({"url": self.url.casefold()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "area": self.area,
            "status": self.status,
            "source_id": self.source_id,
            "text_characters": int(self.text_characters),
            "citations_normalized": list(self.citations_normalized),
            "terms_normalized": list(self.terms_normalized),
            "trust": dict(self.trust),
            "fetched_at": self.fetched_at,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SourceReadingResult:
        return cls(
            url=_clean(payload.get("url")),
            title=_clean(payload.get("title")),
            area=_clean(payload.get("area")),
            status=_clean(payload.get("status")) or "ok",
            source_id=_clean(payload.get("source_id")),
            text_characters=int(payload.get("text_characters") or 0),
            citations_normalized=[_clean(item) for item in payload.get("citations_normalized") or [] if _clean(item)],
            terms_normalized=[_clean(item) for item in payload.get("terms_normalized") or [] if _clean(item)],
            trust=dict(payload.get("trust") or {}),
            fetched_at=_clean(payload.get("fetched_at")),
            warnings=[_clean(item) for item in payload.get("warnings") or [] if _clean(item)],
        )


@dataclass(slots=True)
class LearningSignal:
    """Segnale di valutazione di un ciclo di apprendimento (metriche/allarmi)."""

    name: str
    value: float
    cycle_index: int
    unit: str = ""
    direction: str = "up_good"  # up_good | down_good
    details: dict[str, Any] = field(default_factory=dict)

    def stable_id(self) -> str:
        return stable_id_from({"name": self.name, "cycle_index": self.cycle_index})

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": round(float(self.value), 4),
            "cycle_index": int(self.cycle_index),
            "unit": self.unit,
            "direction": self.direction,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LearningSignal:
        return cls(
            name=_clean(payload.get("name")),
            value=float(payload.get("value") or 0.0),
            cycle_index=int(payload.get("cycle_index") or 0),
            unit=_clean(payload.get("unit")),
            direction=_clean(payload.get("direction")) or "up_good",
            details=dict(payload.get("details") or {}),
        )


__all__ = [
    "LearningSignal",
    "LegalCitation",
    "LegalLanguageProfile",
    "LegalSourceSample",
    "LegalTermObservation",
    "SourceReadingResult",
    "stable_id_from",
]
