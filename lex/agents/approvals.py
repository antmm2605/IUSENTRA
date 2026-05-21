"""Gestione approvazioni per proposte agentiche."""

from __future__ import annotations

from typing import Any

from .models import AgentApproval, AgentProposal, utc_now_iso


def apply_safe_modifications(proposal: AgentProposal, changes: dict[str, Any] | None) -> AgentProposal:
    if not changes:
        return proposal
    allowed = set(proposal.editable_fields)
    if not allowed:
        return proposal
    payload = dict(proposal.payload or {})
    for key, value in changes.items():
        if key in allowed:
            payload[key] = value
    proposal.payload = payload
    return proposal


def mark_approved(proposal: AgentProposal, approval: AgentApproval) -> AgentProposal:
    proposal.status = "approved"
    proposal.approved_by = approval.approved_by
    proposal.approved_at = utc_now_iso()
    return proposal


def mark_rejected(proposal: AgentProposal, *, actor: str, reason: str = "") -> AgentProposal:
    proposal.status = "rejected"
    proposal.rejected_by = actor
    proposal.rejected_at = utc_now_iso()
    proposal.reject_reason = reason
    return proposal

