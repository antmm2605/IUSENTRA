"""Modelli pubblici del Legal Skills Engine.

Il modulo evita riferimenti a path locali o segreti: tutti gli oggetti esposti
passano da ``to_public_dict`` prima di uscire da API o UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


SENSITIVE_KEY_TOKENS = (
    "path",
    "root",
    "secret",
    "token",
    "password",
    "credential",
    "api_key",
    "tenant_id",
    "studio_id",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_string(value: Any, *, max_len: int = 6000) -> str:
    text = " ".join(str(value or "").replace("\x00", " ").split())
    if len(text) > max_len:
        return text[: max_len - 1].rstrip() + "..."
    return text


def asdict_sanitized(value: Any) -> Any:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        cleaned: dict[str, Any] = {}
        for key, raw in value.items():
            safe_key = str(key)
            lowered = safe_key.lower()
            if any(token in lowered for token in SENSITIVE_KEY_TOKENS):
                continue
            cleaned[safe_key] = asdict_sanitized(raw)
        return cleaned
    if isinstance(value, list | tuple | set):
        return [asdict_sanitized(item) for item in value]
    if isinstance(value, str):
        return _clean_string(value)
    return value


@dataclass(slots=True)
class TrustFinding:
    code: str
    severity: str
    message: str
    location: str = ""
    action: str = "review"

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class LegalSkillFrontmatter:
    name: str
    description: str
    argument_hint: str = ""
    user_invocable: bool = True
    allowed_tools: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class LegalSkillCitation:
    label: str
    source_type: str
    reference: str
    reliability: str = "medium"
    url: str = ""
    excerpt: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class CitationProvenance:
    label: str
    source_type: str
    reference: str
    reliability: str = "medium"
    url: str = ""
    excerpt: str = ""
    verification_required: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class LegalSkillFinding:
    title: str
    status: str
    severity: str = "medium"
    summary: str = ""
    recommendation: str = ""
    citations: list[LegalSkillCitation] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class SkillEscalation:
    reason: str
    target_role: str = "avvocato"
    priority: str = "normal"
    blocks_export: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class LegalSkillReviewerNote:
    text: str
    needs_review: bool = True
    blocks_export: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class LegalSkill:
    pack_id: str
    skill_id: str
    name: str
    description: str
    area: str
    body: str = ""
    argument_hint: str = ""
    user_invocable: bool = True
    allowed_tools: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    required_context: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)
    source_mode: str = "balanced"
    builtin: bool = True
    read_only: bool = True
    trust_status: str = "clean"
    trust_findings: list[TrustFinding] = field(default_factory=list)
    version: str = "1.0.0"
    triggers: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    requires_profile: bool = True
    requires_document: bool = False
    requires_fascicolo: bool = False
    frontmatter: LegalSkillFrontmatter | None = None

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict_sanitized(self)
        payload["id"] = self.skill_id
        payload["workflow_markdown_available"] = bool(self.body)
        payload.pop("body", None)
        return payload


@dataclass(slots=True)
class LegalSkillPack:
    pack_id: str
    name: str
    description: str
    area: str
    jurisdiction: str = "IT"
    source_mode: str = "balanced"
    builtin: bool = True
    read_only: bool = True
    version: str = "1.0.0"
    skills: list[LegalSkill] = field(default_factory=list)
    enabled: bool = True
    required_profile_sections: list[str] = field(default_factory=lambda: ["firm_name", "jurisdictions", "practice_areas"])
    minimum_role: str = "legal_skills.leggi"
    created_at: str = ""
    updated_at: str = ""

    def to_public_dict(self, *, include_skills: bool = True) -> dict[str, Any]:
        payload = asdict_sanitized(self)
        payload["id"] = self.pack_id
        if include_skills:
            payload["skills"] = [skill.to_public_dict() for skill in self.skills]
        else:
            payload["skills_count"] = len(self.skills)
            payload.pop("skills", None)
        return payload


@dataclass(slots=True)
class PracticeProfile:
    id: str = "studio"
    tenant_scope: str = "request_context"
    studio_label: str = ""
    jurisdiction_footprint: list[str] = field(default_factory=lambda: ["IT"])
    role: str = "studio_legale"
    attorney_review_contact: str = ""
    source_policy: dict[str, Any] = field(default_factory=dict)
    escalation_matrix: dict[str, Any] = field(default_factory=dict)
    house_style: dict[str, Any] = field(default_factory=dict)
    reviewer_note_policy: str = "review_first"
    output_policy: dict[str, Any] = field(default_factory=dict)
    configured: bool = False
    placeholders_remaining: list[str] = field(default_factory=list)
    updated_by: str = ""
    updated_at: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class MatterPracticeProfile:
    id: str
    fascicolo_id: str
    overrides: dict[str, Any] = field(default_factory=dict)
    cross_matter_context_allowed: bool = False
    configured: bool = False
    updated_at: str = ""

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class LegalSkillProfile:
    profile_id: str = "studio"
    status: str = "incomplete"
    firm_name: str = ""
    jurisdictions: list[str] = field(default_factory=lambda: ["IT"])
    practice_areas: list[str] = field(default_factory=list)
    preferred_source_mode: str = "strict"
    matter_context: dict[str, Any] = field(default_factory=dict)
    verified_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    updated_at: str = ""
    updated_by: str = ""

    def refresh_status(self) -> "LegalSkillProfile":
        required = {
            "firm_name": bool(_clean_string(self.firm_name)),
            "jurisdictions": bool(self.jurisdictions),
            "practice_areas": bool(self.practice_areas),
        }
        self.missing_fields = [key for key, ok in required.items() if not ok]
        self.status = "ready" if not self.missing_fields else "incomplete"
        return self

    def to_public_dict(self) -> dict[str, Any]:
        self.refresh_status()
        return asdict_sanitized(self)


@dataclass(slots=True)
class SkillRunRequest:
    pack_id: str
    skill_id: str
    question: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    documents: list[dict[str, Any]] = field(default_factory=list)
    requested_source_mode: str = ""
    matter_id: str = ""
    allow_external_sources: bool = False

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SkillRunRequest":
        context = payload.get("context") if isinstance(payload.get("context"), Mapping) else {}
        documents = payload.get("documents") if isinstance(payload.get("documents"), list) else []
        return cls(
            pack_id=_clean_string(payload.get("pack_id"), max_len=120),
            skill_id=_clean_string(payload.get("skill_id"), max_len=120),
            question=_clean_string(payload.get("question"), max_len=6000),
            context={str(key): value for key, value in context.items() if str(key) not in {"tenant_id", "studio_id"}},
            documents=[doc for doc in documents if isinstance(doc, Mapping)][:20],
            requested_source_mode=_clean_string(payload.get("source_mode") or payload.get("requested_source_mode"), max_len=40),
            matter_id=_clean_string(payload.get("matter_id"), max_len=160),
            allow_external_sources=bool(payload.get("allow_external_sources", False)),
        )

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class SkillRunResult:
    run_id: str
    pack_id: str
    skill_id: str
    status: str
    question: str
    answer: str
    findings: list[LegalSkillFinding] = field(default_factory=list)
    citations: list[LegalSkillCitation] = field(default_factory=list)
    reviewer_note: LegalSkillReviewerNote = field(default_factory=lambda: LegalSkillReviewerNote(text="Bozza da verificare prima dell'uso."))
    confidence: str = "medium"
    source_mode: str = "balanced"
    needs_review: bool = True
    disable_exports: bool = False
    approved_at: str = ""
    approved_by: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class TrustCheckResult:
    verdict: str
    findings: list[TrustFinding] = field(default_factory=list)
    material_concern: bool = False
    refused: bool = False
    reviewer_note: str = ""
    checked_at: str = field(default_factory=utc_now_iso)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class ScheduledAgentDefinition:
    agent_id: str
    name: str
    description: str
    skill_ref: str
    enabled: bool = False
    read_only: bool = True
    required_permission: str = "legal_skills.scheduled.esegui"

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class ScheduledLegalAgent:
    id: str
    name: str
    description: str
    skill_ref: str
    enabled: bool = False
    read_only: bool = True
    required_permission: str = "legal_skills.scheduled.esegui"

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


@dataclass(slots=True)
class ScheduledAgentRunResult:
    agent_id: str
    run_id: str
    status: str
    summary: str
    reviewer_note: LegalSkillReviewerNote
    citations: list[LegalSkillCitation] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now_iso)

    def to_public_dict(self) -> dict[str, Any]:
        return asdict_sanitized(self)


__all__ = [
    "CitationProvenance",
    "LegalSkill",
    "LegalSkillCitation",
    "LegalSkillFinding",
    "LegalSkillFrontmatter",
    "LegalSkillPack",
    "LegalSkillProfile",
    "LegalSkillReviewerNote",
    "MatterPracticeProfile",
    "PracticeProfile",
    "ScheduledAgentDefinition",
    "ScheduledAgentRunResult",
    "ScheduledLegalAgent",
    "SkillEscalation",
    "SkillRunRequest",
    "SkillRunResult",
    "TrustCheckResult",
    "TrustFinding",
    "asdict_sanitized",
    "utc_now_iso",
]
