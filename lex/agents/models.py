"""Modelli serializzabili per Lex Workflow Agents."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


AgentRunStatus = Literal[
    "draft",
    "running",
    "needs_approval",
    "approved",
    "executed",
    "blocked",
    "failed",
    "cancelled",
]

AgentStepStatus = Literal["pending", "running", "done", "needs_approval", "blocked", "failed"]
AgentProposalStatus = Literal["pending", "approved", "rejected", "executed", "blocked"]

RUN_STATUSES = frozenset({"draft", "running", "needs_approval", "approved", "executed", "blocked", "failed", "cancelled"})
STEP_STATUSES = frozenset({"pending", "running", "done", "needs_approval", "blocked", "failed"})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


@dataclass(slots=True)
class AgentStep:
    step_key: str
    title: str
    tool_name: str
    input_json: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("step"))
    status: AgentStepStatus = "pending"
    mutates_state: bool = False
    approval_required: bool = False
    required_permissions: tuple[str, ...] = ()
    output_json: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    proposal_id: str = ""
    baseline_minutes: float = 0.0
    preview_minutes: float = 0.0
    review_minutes: float = 0.0
    correction_minutes: float = 0.0
    risk_level: str = "low"
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["required_permissions"] = list(self.required_permissions)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentStep":
        payload = dict(data or {})
        payload["required_permissions"] = tuple(payload.get("required_permissions") or ())
        return cls(**{key: value for key, value in payload.items() if key in cls.__dataclass_fields__})


@dataclass(slots=True)
class AgentPlan:
    workflow_code: str
    title: str
    description: str
    steps: list[AgentStep]
    id: str = field(default_factory=lambda: new_id("plan"))
    fascicolo_id: str = ""
    risk_level: str = "medium"
    baseline_minutes: float = 0.0
    expected_review_minutes: float = 0.0
    expected_correction_minutes: float = 0.0
    confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["steps"] = [step.to_dict() for step in self.steps]
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentPlan":
        payload = dict(data or {})
        payload["steps"] = [AgentStep.from_dict(item) for item in payload.get("steps") or []]
        return cls(**{key: value for key, value in payload.items() if key in cls.__dataclass_fields__})


@dataclass(slots=True)
class AgentProposal:
    run_id: str
    step_id: str
    tool_name: str
    title: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("proposal"))
    status: AgentProposalStatus = "pending"
    action_type: str = ""
    impact: str = ""
    risk_level: str = "medium"
    editable_fields: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_iso)
    approved_by: str = ""
    approved_at: str = ""
    rejected_by: str = ""
    rejected_at: str = ""
    reject_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["editable_fields"] = list(self.editable_fields)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentProposal":
        payload = dict(data or {})
        payload["editable_fields"] = tuple(payload.get("editable_fields") or ())
        return cls(**{key: value for key, value in payload.items() if key in cls.__dataclass_fields__})


@dataclass(slots=True)
class AgentMetric:
    workflow_code: str
    run_id: str
    baseline_minutes: float
    preview_minutes: float = 0.0
    review_minutes: float = 0.0
    correction_minutes: float = 0.0
    saved_minutes: float = 0.0
    saving_percentage: float = 0.0
    target_80_met: bool = False
    accepted_actions: int = 0
    rejected_actions: int = 0
    id: str = field(default_factory=lambda: new_id("metric"))
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMetric":
        return cls(**{key: value for key, value in dict(data or {}).items() if key in cls.__dataclass_fields__})


@dataclass(slots=True)
class AgentRun:
    workflow_code: str
    created_by: str
    plan: AgentPlan
    tenant_scope: str
    id: str = field(default_factory=lambda: new_id("run"))
    fascicolo_id: str = ""
    status: AgentRunStatus = "draft"
    created_at: str = field(default_factory=utc_now_iso)
    started_at: str = ""
    completed_at: str = ""
    risk_level: str = "medium"
    confidence: float = 0.0
    evidence_json: dict[str, Any] = field(default_factory=dict)
    proposals: list[AgentProposal] = field(default_factory=list)
    result_json: dict[str, Any] = field(default_factory=dict)
    metrics: AgentMetric | None = None
    audit_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["plan"] = self.plan.to_dict()
        payload["proposals"] = [proposal.to_dict() for proposal in self.proposals]
        payload["metrics"] = self.metrics.to_dict() if self.metrics else None
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentRun":
        payload = dict(data or {})
        payload["plan"] = AgentPlan.from_dict(payload.get("plan") or {})
        payload["proposals"] = [AgentProposal.from_dict(item) for item in payload.get("proposals") or []]
        metric = payload.get("metrics")
        payload["metrics"] = AgentMetric.from_dict(metric) if isinstance(metric, dict) else None
        return cls(**{key: value for key, value in payload.items() if key in cls.__dataclass_fields__})


@dataclass(slots=True)
class AgentApproval:
    run_id: str
    approved_step_ids: list[str]
    approved_by: str
    modifications: dict[str, dict[str, Any]] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("approval"))
    created_at: str = field(default_factory=utc_now_iso)
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
