"""Estensione coverage per inventario XSD, fonti, schede e lifecycle."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


class ProcedureGapType(str, Enum):
    MISSING_XSD_OBJECT = "MISSING_XSD_OBJECT"
    MISSING_XSD_MAPPING = "MISSING_XSD_MAPPING"
    MISSING_SOURCE_EVIDENCE = "MISSING_SOURCE_EVIDENCE"
    MISSING_KNOWLEDGE_CARD = "MISSING_KNOWLEDGE_CARD"
    MISSING_LIFECYCLE = "MISSING_LIFECYCLE"
    MISSING_SIGNATURE_RULES = "MISSING_SIGNATURE_RULES"
    MISSING_DEPOSIT_RULES = "MISSING_DEPOSIT_RULES"
    MISSING_RECEIPT_RULES = "MISSING_RECEIPT_RULES"
    MISSING_ACCEPTANCE_RULES = "MISSING_ACCEPTANCE_RULES"
    MISSING_POST_ACCEPTANCE_RULES = "MISSING_POST_ACCEPTANCE_RULES"
    MISSING_NOTIFICATION_RULES = "MISSING_NOTIFICATION_RULES"
    MISSING_RELATA_RULES = "MISSING_RELATA_RULES"
    MISSING_PROOF_RULES = "MISSING_PROOF_RULES"
    MISSING_EVIDENCE_RULES = "MISSING_EVIDENCE_RULES"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


PROCEDURE_GAP_TYPES: tuple[str, ...] = tuple(gap.value for gap in ProcedureGapType)

EXTENDED_BLOCKS: tuple[str, ...] = (
    "xsd_object",
    "xsd_mapping",
    "source_evidence",
    "knowledge_card",
    "lifecycle_template",
    "lifecycle_steps",
    "signature_rules",
    "deposit_rules",
    "receipt_rules",
    "acceptance_rules",
    "post_acceptance_rules",
    "notification_rules",
    "relata_rules",
    "proof_deposit_rules",
    "evidence_rules",
)

GAP_BY_BLOCK = {
    "xsd_object": ProcedureGapType.MISSING_XSD_OBJECT.value,
    "xsd_mapping": ProcedureGapType.MISSING_XSD_MAPPING.value,
    "source_evidence": ProcedureGapType.MISSING_SOURCE_EVIDENCE.value,
    "knowledge_card": ProcedureGapType.MISSING_KNOWLEDGE_CARD.value,
    "lifecycle_template": ProcedureGapType.MISSING_LIFECYCLE.value,
    "lifecycle_steps": ProcedureGapType.MISSING_LIFECYCLE.value,
    "signature_rules": ProcedureGapType.MISSING_SIGNATURE_RULES.value,
    "deposit_rules": ProcedureGapType.MISSING_DEPOSIT_RULES.value,
    "receipt_rules": ProcedureGapType.MISSING_RECEIPT_RULES.value,
    "acceptance_rules": ProcedureGapType.MISSING_ACCEPTANCE_RULES.value,
    "post_acceptance_rules": ProcedureGapType.MISSING_POST_ACCEPTANCE_RULES.value,
    "notification_rules": ProcedureGapType.MISSING_NOTIFICATION_RULES.value,
    "relata_rules": ProcedureGapType.MISSING_RELATA_RULES.value,
    "proof_deposit_rules": ProcedureGapType.MISSING_PROOF_RULES.value,
    "evidence_rules": ProcedureGapType.MISSING_EVIDENCE_RULES.value,
}


@dataclass(frozen=True)
class ExtendedCoverage:
    procedure_code: str
    xsd_code: str | None
    status: str
    ready: bool
    blocks: dict[str, bool]
    missing_blocks: list[str]
    review_required: bool
    review_satisfied: bool
    auto_publish_eligible: bool
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _prefix(xsd_code: str | None) -> str:
    return str(xsd_code or "")[:3]


def _risk_for_xsd(xsd_code: str | None) -> str:
    if _prefix(xsd_code) == "050":
        return "HIGH"
    if _prefix(xsd_code) in {"017", "051", "052", "053", "055", "059"}:
        return "HIGH"
    return "MEDIUM"


def _steps_by_type(repo: ProcedureLifecycleRepository, template_id: int) -> set[str]:
    return {str(row.get("step_type") or "") for row in repo.list_lifecycle_steps(template_id)}


def compute_extended_coverage(
    repo: ProcedureLifecycleRepository,
    procedure_code: str,
    xsd_code: str | None,
) -> dict[str, Any]:
    repo.ensure_extended_schema()
    xsd = repo.get_xsd_object(xsd_code or "") if xsd_code else None
    mappings = repo.list_xsd_mappings(xsd_code or "", procedure_code)
    sources = repo.list_source_evidence(procedure_code, xsd_code)
    cards = repo.list_knowledge_cards(procedure_code, xsd_code or "")
    templates = repo.list_lifecycle_templates(xsd_code or "", procedure_code)
    template = templates[0] if templates else None
    step_types = _steps_by_type(repo, int(template["id"])) if template else set()
    prefix = _prefix(xsd_code)
    notification_expected = prefix in {"010", "020", "030", "050"} or prefix in {
        "011",
        "012",
        "014",
        "015",
        "017",
        "019",
        "051",
        "052",
        "053",
        "055",
        "059",
    }
    proof_expected = prefix in {"010", "030", "050"}
    has_reviewed_mapping = any(str(row.get("review_status")) == "validated" for row in mappings)
    has_reviewed_card = any(str(row.get("status")) in {"approved", "published"} for row in cards)
    has_official_or_technical_source = any(
        str(row.get("source_type")) in {"official", "technical", "internal", "licensed_database"}
        and str(row.get("review_status") or "needs_review") in {"validated", "approved"}
        for row in sources
    )

    blocks = {
        "xsd_object": bool(xsd and int(xsd.get("active") or 0) == 1),
        "xsd_mapping": bool(mappings),
        "source_evidence": bool(sources),
        "knowledge_card": bool(cards),
        "lifecycle_template": bool(template),
        "lifecycle_steps": bool(step_types),
        "signature_rules": "SIGNATURE_DECISION" in step_types and "SIGNATURE" in step_types,
        "deposit_rules": {"PACKAGE_BUILD", "PACKAGE_VALIDATE", "DEPOSIT_SEND"}.issubset(step_types),
        "receipt_rules": "RECEIPT_WAIT" in step_types,
        "acceptance_rules": "ACCEPTANCE_CHECK" in step_types,
        "post_acceptance_rules": "POST_ACCEPTANCE_REVIEW" in step_types,
        "notification_rules": (not notification_expected) or "NOTIFICATION_DECISION" in step_types,
        "relata_rules": (not notification_expected) or "RELATA" in step_types or prefix not in {"010", "030", "050"},
        "proof_deposit_rules": (not proof_expected) or "PROOF_DEPOSIT" in step_types,
        "evidence_rules": bool(step_types and {"PROOF_COLLECTION", "RECEIPT_WAIT", "SIGNATURE"} & step_types),
    }
    missing = [block for block in EXTENDED_BLOCKS if not blocks.get(block)]
    review_required = True
    review_satisfied = has_reviewed_mapping and has_reviewed_card and has_official_or_technical_source
    risk_level = _risk_for_xsd(xsd_code)
    ready = not missing and review_satisfied
    status = "READY" if ready else "PARTIAL" if any(blocks.values()) else "EMPTY"

    return ExtendedCoverage(
        procedure_code=procedure_code,
        xsd_code=xsd_code,
        status=status,
        ready=ready,
        blocks=blocks,
        missing_blocks=missing + ([] if review_satisfied else ["human_review"]),
        review_required=review_required,
        review_satisfied=review_satisfied,
        auto_publish_eligible=False if review_required or risk_level in {"HIGH", "SPECIALIST"} else ready,
        risk_level=risk_level,
    ).to_dict()


def enqueue_extended_gaps(repo: ProcedureLifecycleRepository, coverage: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    missing_blocks = list(coverage.get("missing_blocks") or [])
    xsd_code = str(coverage.get("xsd_code") or "")
    procedure_code = str(coverage.get("procedure_code") or "")
    xsd = repo.get_xsd_object(xsd_code) if xsd_code else None
    for block in missing_blocks:
        gap_type = ProcedureGapType.NEEDS_HUMAN_REVIEW.value if block == "human_review" else GAP_BY_BLOCK.get(block)
        if not gap_type:
            continue
        payload = {
            "xsd_code": xsd_code,
            "xsd_label": (xsd or {}).get("xsd_label"),
            "procedure_code": procedure_code,
            "missing_blocks": missing_blocks,
            "required_action": "review_avvocato" if gap_type == "NEEDS_HUMAN_REVIEW" else f"complete_{block}",
            "risk_level": coverage.get("risk_level", "MEDIUM"),
            "human_review_required": True,
        }
        gap_id = repo.add_coverage_gap(
            subbranch_code=procedure_code or f"XSD:{xsd_code}",
            gap_type=gap_type,
            priority_score=120 if gap_type == "NEEDS_HUMAN_REVIEW" else 100,
            gap_payload=payload,
        )
        gaps.append({"id": gap_id, "gap_type": gap_type, "gap_payload": payload})
    return gaps


def list_procedure_inventory_coverage(repo: ProcedureLifecycleRepository) -> list[dict[str, Any]]:
    repo.ensure_extended_schema()
    rows: list[dict[str, Any]] = []
    for xsd in repo.list_xsd_objects(active_only=True):
        mappings = repo.list_xsd_mappings(str(xsd["xsd_code"]))
        if mappings:
            for mapping in mappings:
                rows.append(
                    compute_extended_coverage(
                        repo,
                        str(mapping["procedure_code"]),
                        str(xsd["xsd_code"]),
                    )
                )
        else:
            rows.append(
                compute_extended_coverage(
                    repo,
                    "",
                    str(xsd["xsd_code"]),
                )
            )
    return rows
