"""Data contracts for Lex operational knowledge."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True, slots=True)
class OperationalSourceDefinition:
    source_id: str
    display_name: str
    source_type: str
    category: str
    tenant_keys: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    repository_module: str = ""
    api_surface: str = ""
    deterministic_tools: tuple[str, ...] = ()
    internal: bool = True
    sensitive: bool = True
    document_retrieval: bool = False
    official_public_source: bool = False
    enabled_by_default: bool = True
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationalQueryContext:
    tenant_id: str
    user_id: str
    username: str = ""
    user: Any = None
    permissions: set[str] = field(default_factory=set)
    multi_tenant: bool = False
    tenant_context_available: bool = True
    request_id: str = ""
    source: str = "explicit"

    def has_permission(self, permission: str) -> bool:
        if not permission:
            return True
        checker = getattr(self.user, "ha_permesso", None)
        if callable(checker):
            return bool(checker(permission))
        return permission in self.permissions

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "username": self.username,
            "multi_tenant": self.multi_tenant,
            "source": self.source,
        }


@dataclass(slots=True)
class PermissionDecision:
    allowed: bool
    source_id: str
    reason: str = ""
    missing_permissions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationalSourceReference:
    source_id: str
    source_name: str
    source_type: str
    object_type: str = ""
    object_id: str = ""
    title: str = ""
    confidence: float = 0.0
    internal: bool = True
    permission_applied: str = ""
    retrieved_at: str = field(default_factory=utc_now_iso)
    limitations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        pieces = [self.source_name, self.object_type, self.title or self.object_id]
        return " - ".join(str(piece).strip() for piece in pieces if str(piece or "").strip())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationalObjectReference:
    object_type: str
    object_id: str
    label: str = ""
    source_id: str = ""
    action_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationalToolResult:
    ok: bool
    source_id: str
    data: Any = None
    sources: list[OperationalSourceReference] = field(default_factory=list)
    objects: list[OperationalObjectReference] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    permission: PermissionDecision | None = None
    blocked_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "source_id": self.source_id,
            "data": self.data,
            "sources": [source.to_dict() for source in self.sources],
            "objects": [obj.to_dict() for obj in self.objects],
            "coverage_gaps": list(self.coverage_gaps),
            "warnings": list(self.warnings),
            "permission": self.permission.to_dict() if self.permission else None,
            "blocked_reason": self.blocked_reason,
        }


@dataclass(frozen=True, slots=True)
class OperationalRoute:
    route_id: str
    intent: str
    source_ids: tuple[str, ...]
    entity_query: str = ""
    requires_clarification: bool = False
    blocks_legal_action: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class OperationalAnswer:
    handled: bool
    answer: str
    route: OperationalRoute | None = None
    sources: list[OperationalSourceReference] = field(default_factory=list)
    objects: list[OperationalObjectReference] = field(default_factory=list)
    confidence: float = 0.0
    coverage_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    permissions_applied: list[str] = field(default_factory=list)
    fallback_triggered: bool = False
    blocked_reason: str = ""
    audit_event_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "handled": self.handled,
            "answer": self.answer,
            "route": self.route.to_dict() if self.route else None,
            "sources": [source.to_dict() for source in self.sources],
            "objects": [obj.to_dict() for obj in self.objects],
            "confidence": self.confidence,
            "coverage_gaps": list(self.coverage_gaps),
            "warnings": list(self.warnings),
            "next_actions": list(self.next_actions),
            "permissions_applied": list(self.permissions_applied),
            "fallback_triggered": self.fallback_triggered,
            "blocked_reason": self.blocked_reason,
            "audit_event_id": self.audit_event_id,
            "metadata": dict(self.metadata),
        }
