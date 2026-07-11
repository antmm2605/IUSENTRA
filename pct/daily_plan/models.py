"""Modelli puri del piano del giorno (Lex Oggi).

Dataclass serializzabili e prive di I/O. I metadata vengono sempre
redatti: mai path filesystem, segreti, token, IBAN o codici fiscali nei
payload o nei log.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

PRIORITIES = ("P0", "P1", "P2", "P3")

SIGNAL_STATUSES = ("active", "resolved", "obsolete")

ITEM_STATUSES = (
    "proposed",
    "accepted",
    "scheduled",
    "in_progress",
    "completed",
    "delegated",
    "snoozed",
    "rejected",
    "obsolete",
    "needs_review",
)

# Transizioni ammesse dalla state machine delle attività (azioni umane).
ITEM_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "proposed": ("accepted", "completed", "delegated", "snoozed", "rejected", "in_progress"),
    "needs_review": ("accepted", "completed", "delegated", "snoozed", "rejected"),
    "accepted": ("in_progress", "completed", "delegated", "snoozed", "rejected"),
    "scheduled": ("in_progress", "completed", "delegated", "snoozed", "rejected"),
    "in_progress": ("completed", "delegated", "snoozed", "rejected"),
    "snoozed": ("accepted", "in_progress", "completed", "delegated", "rejected"),
    "delegated": ("accepted", "in_progress", "completed", "rejected"),
    "completed": (),
    "rejected": (),
    "obsolete": (),
}

# Stati decisi da una persona: la rigenerazione del piano non li sovrascrive.
HUMAN_STATUSES = frozenset(
    {"accepted", "in_progress", "completed", "delegated", "snoozed", "rejected"}
)

SOURCE_TYPES = (
    "pec",
    "case_presidio",
    "agenda",
    "scadenziario",
    "deposit",
    "notification",
    "economic",
    "health",
)

COVERAGE_STATUSES = ("complete", "stale", "unavailable", "never")

_FORBIDDEN_METADATA_KEYS = re.compile(
    r"(password|passwd|secret|token|api_key|apikey|authorization|iban|codice_fiscale|"
    r"cf_|_cf\b|filesystem|filepath|file_path|abs_path)",
    re.IGNORECASE,
)
_PATH_LIKE = re.compile(r"(?:[A-Za-z]:\\\S+)|(?:(?<![\w./])/(?:home|opt|var|etc|root|data|tmp)/\S*)")
_IBAN_LIKE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_CF_LIKE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b")


def redact_text(value: Any, *, max_len: int = 400) -> str:
    """Redige un testo per payload/log: niente IBAN, CF o path assoluti."""
    testo = " ".join(str(value or "").split())
    testo = _IBAN_LIKE.sub("[dato riservato]", testo)
    testo = _CF_LIKE.sub("[dato riservato]", testo)
    testo = _PATH_LIKE.sub("[percorso omesso]", testo)
    return testo[:max_len]


def redact_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Ritorna una copia dei metadata senza chiavi/valori sensibili."""
    out: dict[str, Any] = {}
    for key, value in dict(metadata or {}).items():
        if _FORBIDDEN_METADATA_KEYS.search(str(key)):
            continue
        if isinstance(value, dict):
            out[str(key)] = redact_metadata(value)
        elif isinstance(value, (list, tuple)):
            out[str(key)] = [
                redact_metadata(v) if isinstance(v, dict) else redact_text(v)
                for v in value
            ][:20]
        elif isinstance(value, (int, float, bool)) or value is None:
            out[str(key)] = value
        else:
            out[str(key)] = redact_text(value)
    return out


@dataclass
class SignalEvidence:
    """Evidenza probatoria di un segnale (riferimento a una fonte reale)."""

    source_type: str
    source_id: str = ""
    label: str = ""
    timestamp: str = ""
    audit_ref: str = ""
    href: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["label"] = redact_text(data.get("label"))
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SignalEvidence":
        return cls(
            source_type=str(data.get("source_type") or ""),
            source_id=str(data.get("source_id") or ""),
            label=str(data.get("label") or ""),
            timestamp=str(data.get("timestamp") or ""),
            audit_ref=str(data.get("audit_ref") or ""),
            href=str(data.get("href") or ""),
            confidence=float(data.get("confidence") or 0.0),
        )


@dataclass
class OperationalSignal:
    """Segnale operativo normalizzato prodotto da un collettore."""

    id: str
    tenant_id: str
    source_type: str
    kind: str
    title: str
    dedupe_key: str
    source_id: str = ""
    source_version: str = ""
    fascicolo_id: str = ""
    cliente_id: str = ""
    lawyer_hint: str = ""
    responsible_user_id: str = ""
    description: str = ""
    reason: str = ""
    event_at: str = ""
    due_at: str = ""
    legal_risk: str = ""
    priority_hint: str = ""
    blocking: bool = False
    peremptory: bool = False
    confidence: float = 0.0
    status: str = "active"
    evidence: list[SignalEvidence] = field(default_factory=list)
    href: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        self.title = redact_text(self.title, max_len=200)
        self.description = redact_text(self.description)
        self.reason = redact_text(self.reason)
        self.metadata = redact_metadata(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [e.to_dict() for e in self.evidence]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OperationalSignal":
        evidence = [SignalEvidence.from_dict(e) for e in (data.get("evidence") or [])]
        return cls(
            id=str(data.get("id") or ""),
            tenant_id=str(data.get("tenant_id") or ""),
            source_type=str(data.get("source_type") or ""),
            kind=str(data.get("kind") or ""),
            title=str(data.get("title") or ""),
            dedupe_key=str(data.get("dedupe_key") or ""),
            source_id=str(data.get("source_id") or ""),
            source_version=str(data.get("source_version") or ""),
            fascicolo_id=str(data.get("fascicolo_id") or ""),
            cliente_id=str(data.get("cliente_id") or ""),
            lawyer_hint=str(data.get("lawyer_hint") or ""),
            responsible_user_id=str(data.get("responsible_user_id") or ""),
            description=str(data.get("description") or ""),
            reason=str(data.get("reason") or ""),
            event_at=str(data.get("event_at") or ""),
            due_at=str(data.get("due_at") or ""),
            legal_risk=str(data.get("legal_risk") or ""),
            priority_hint=str(data.get("priority_hint") or ""),
            blocking=bool(data.get("blocking")),
            peremptory=bool(data.get("peremptory")),
            confidence=float(data.get("confidence") or 0.0),
            status=str(data.get("status") or "active"),
            evidence=evidence,
            href=str(data.get("href") or ""),
            metadata=dict(data.get("metadata") or {}),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


@dataclass
class DailyWorkItem:
    """Attività del piano giornaliero (una per gruppo di segnali dedotti)."""

    id: str
    tenant_id: str
    target_date: str
    title: str
    action_kind: str
    dedupe_key: str
    priority: str = "P3"
    item_rank: int = 0
    assigned_user_id: str = ""
    assigned_lawyer_label: str = ""
    plan_version: str = ""
    sector: str = ""
    status: str = "proposed"
    reason: str = ""
    priority_reason: str = ""
    priority_rule: str = ""
    fascicolo_id: str = ""
    fascicolo_label: str = ""
    cliente_id: str = ""
    cliente_label: str = ""
    due_at: str = ""
    blocking: bool = False
    peremptory: bool = False
    confidence: float = 0.0
    review_required: bool = False
    scheduled_start: str = ""
    estimated_minutes: int = 0
    in_backlog: bool = False
    source_signal_ids: list[str] = field(default_factory=list)
    evidence: list[SignalEvidence] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=list)
    href: str = ""
    snoozed_until: str = ""
    status_actor: str = ""
    status_note: str = ""
    status_updated_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if self.priority not in PRIORITIES:
            self.priority = "P3"
        if self.status not in ITEM_STATUSES:
            self.status = "proposed"
        self.title = redact_text(self.title, max_len=200)
        self.reason = redact_text(self.reason)
        self.priority_reason = redact_text(self.priority_reason)
        self.status_note = redact_text(self.status_note)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [e.to_dict() for e in self.evidence]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DailyWorkItem":
        evidence = [SignalEvidence.from_dict(e) for e in (data.get("evidence") or [])]
        return cls(
            id=str(data.get("id") or ""),
            tenant_id=str(data.get("tenant_id") or ""),
            target_date=str(data.get("target_date") or ""),
            title=str(data.get("title") or ""),
            action_kind=str(data.get("action_kind") or ""),
            dedupe_key=str(data.get("dedupe_key") or ""),
            priority=str(data.get("priority") or "P3"),
            item_rank=int(data.get("item_rank") or 0),
            assigned_user_id=str(data.get("assigned_user_id") or ""),
            assigned_lawyer_label=str(data.get("assigned_lawyer_label") or ""),
            plan_version=str(data.get("plan_version") or ""),
            sector=str(data.get("sector") or ""),
            status=str(data.get("status") or "proposed"),
            reason=str(data.get("reason") or ""),
            priority_reason=str(data.get("priority_reason") or ""),
            priority_rule=str(data.get("priority_rule") or ""),
            fascicolo_id=str(data.get("fascicolo_id") or ""),
            fascicolo_label=str(data.get("fascicolo_label") or ""),
            cliente_id=str(data.get("cliente_id") or ""),
            cliente_label=str(data.get("cliente_label") or ""),
            due_at=str(data.get("due_at") or ""),
            blocking=bool(data.get("blocking")),
            peremptory=bool(data.get("peremptory")),
            confidence=float(data.get("confidence") or 0.0),
            review_required=bool(data.get("review_required")),
            scheduled_start=str(data.get("scheduled_start") or ""),
            estimated_minutes=int(data.get("estimated_minutes") or 0),
            in_backlog=bool(data.get("in_backlog")),
            source_signal_ids=[str(x) for x in (data.get("source_signal_ids") or [])],
            evidence=evidence,
            available_actions=[str(x) for x in (data.get("available_actions") or [])],
            href=str(data.get("href") or ""),
            snoozed_until=str(data.get("snoozed_until") or ""),
            status_actor=str(data.get("status_actor") or ""),
            status_note=str(data.get("status_note") or ""),
            status_updated_at=str(data.get("status_updated_at") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
        )


@dataclass
class SourceCoverage:
    """Stato di copertura di una fonte del piano."""

    source_type: str
    status: str = "never"  # complete|stale|unavailable|never
    watermark: str = ""
    last_success_at: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["note"] = redact_text(data.get("note"))
        return data

    @property
    def reliable(self) -> bool:
        return self.status == "complete"


@dataclass
class DailyPlan:
    """Piano giornaliero per un utente (o coda studio con user_id='')."""

    id: str
    tenant_id: str
    target_date: str
    user_id: str = ""
    plan_version: str = ""
    generated_at: str = ""
    generation_mode: str = "full"
    freshness: dict[str, Any] = field(default_factory=dict)
    coverage: list[SourceCoverage] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    work_items: list[DailyWorkItem] = field(default_factory=list)
    fixed_agenda_items: list[dict[str, Any]] = field(default_factory=list)
    backlog: list[DailyWorkItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    source_watermarks: dict[str, str] = field(default_factory=dict)
    lex_summary: str = ""
    lex_summary_version: str = ""

    @property
    def coverage_complete(self) -> bool:
        return bool(self.coverage) and all(c.reliable for c in self.coverage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "target_date": self.target_date,
            "user_id": self.user_id,
            "plan_version": self.plan_version,
            "generated_at": self.generated_at,
            "generation_mode": self.generation_mode,
            "freshness": dict(self.freshness),
            "coverage": [c.to_dict() for c in self.coverage],
            "coverage_complete": self.coverage_complete,
            "summary": dict(self.summary),
            "work_items": [w.to_dict() for w in self.work_items],
            "fixed_agenda_items": list(self.fixed_agenda_items),
            "backlog": [w.to_dict() for w in self.backlog],
            "warnings": [redact_text(w) for w in self.warnings],
            "source_watermarks": dict(self.source_watermarks),
            "lex_summary": self.lex_summary,
            "lex_summary_version": self.lex_summary_version,
        }


__all__ = [
    "COVERAGE_STATUSES",
    "DailyPlan",
    "DailyWorkItem",
    "HUMAN_STATUSES",
    "ITEM_STATUSES",
    "ITEM_STATUS_TRANSITIONS",
    "OperationalSignal",
    "PRIORITIES",
    "SIGNAL_STATUSES",
    "SOURCE_TYPES",
    "SignalEvidence",
    "SourceCoverage",
    "redact_metadata",
    "redact_text",
]
