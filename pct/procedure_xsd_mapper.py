"""Mapping prudente tra codici XSD/PST e procedure operative IUSENTRA."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pct.legal_platform_catalog import PROCEDURE_REGISTRY, LegalOperationalProcedure
from pct.procedure_lifecycle_repository import ProcedureLifecycleRepository


CAUTELARI_PREFIXES = {"011", "012", "014", "015", "017", "019", "051", "052", "053", "055", "059"}


@dataclass(frozen=True)
class MappingCandidate:
    xsd_code: str
    procedure_code: str
    channel_code: str
    registry_code: str
    workflow_code: str
    is_default: int
    confidence_score: int
    mapping_source: str
    review_status: str
    notes: str

    def to_row(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MappingReport:
    dry_run: bool
    total_xsd_objects: int
    automatic_mappings: int
    needs_review: int
    validated: int
    applied: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _procedure_to_candidate(
    xsd_code: str,
    proc: LegalOperationalProcedure,
    *,
    confidence_score: int,
    review_status: str,
    notes: str,
) -> MappingCandidate:
    return MappingCandidate(
        xsd_code=xsd_code,
        procedure_code=proc.code,
        channel_code=proc.channel_code,
        registry_code=proc.registry_code,
        workflow_code=proc.workflow_code,
        is_default=1,
        confidence_score=confidence_score,
        mapping_source="RULE",
        review_status=review_status,
        notes=notes,
    )


def _placeholder_candidate(
    xsd_code: str,
    procedure_code: str,
    *,
    confidence_score: int,
    notes: str,
    channel_code: str = "PCT_CIVILE",
    registry_code: str = "RG_CIVILE",
    workflow_code: str = "WF_PCT_NEEDS_REVIEW",
) -> MappingCandidate:
    return MappingCandidate(
        xsd_code=xsd_code,
        procedure_code=procedure_code,
        channel_code=channel_code,
        registry_code=registry_code,
        workflow_code=workflow_code,
        is_default=1,
        confidence_score=confidence_score,
        mapping_source="RULE",
        review_status="needs_review",
        notes=notes,
    )


def _find_registry_match(keywords: tuple[str, ...], procedure_registry: dict[str, Any]) -> LegalOperationalProcedure | None:
    lowered = tuple(keyword.lower() for keyword in keywords)
    for proc in procedure_registry.values():
        name = _clean(getattr(proc, "name", "")).lower()
        workflow = _clean(getattr(proc, "workflow_code", "")).lower()
        code = _clean(getattr(proc, "code", "")).lower()
        haystack = f"{name} {workflow} {code}"
        if all(keyword in haystack for keyword in lowered):
            return proc
    for proc in procedure_registry.values():
        haystack = _clean(getattr(proc, "name", "")).lower()
        if any(keyword in haystack for keyword in lowered):
            return proc
    return None


def infer_mapping_for_xsd(
    xsd_object: dict[str, Any],
    procedure_registry: dict[str, Any] | None = None,
) -> MappingCandidate:
    registry = procedure_registry or PROCEDURE_REGISTRY
    xsd_code = _clean(xsd_object.get("xsd_code"))
    label = _clean(xsd_object.get("xsd_label")).lower()
    prefix = xsd_code[:3]

    if prefix == "010":
        proc = _find_registry_match(("ingiun",), registry)
        if proc:
            return _procedure_to_candidate(
                xsd_code,
                proc,
                confidence_score=85,
                review_status="needs_review",
                notes="Prefisso 010 riconosciuto come ingiunzione ante causam; mapping da revisionare dall'avvocato.",
            )
        return _placeholder_candidate(
            xsd_code,
            "PROC_PCT_INGIUNZIONE_ANTE_CAUSAM_NEEDS_REVIEW",
            confidence_score=80,
            workflow_code="WF_PCT_INGIUNZIONE_ANTE_CAUSAM",
            notes="Prefisso 010 riconosciuto; procedura operativa puntuale non trovata nel registry, placeholder needs_review.",
        )

    if prefix == "050":
        proc = _find_registry_match(("ingiun", "soc"), registry) or _find_registry_match(("bancar",), registry)
        if proc:
            return _procedure_to_candidate(
                xsd_code,
                proc,
                confidence_score=85,
                review_status="needs_review",
                notes="Prefisso 050 riconosciuto come ingiunzione societaria/finanziaria/bancaria; review obbligatoria.",
            )
        return _placeholder_candidate(
            xsd_code,
            "PROC_PCT_INGIUNZIONE_SOCIETARIA_FINANZIARIA_NEEDS_REVIEW",
            confidence_score=80,
            workflow_code="WF_PCT_INGIUNZIONE_HIGH_REVIEW",
            notes="Prefisso 050 riconosciuto; mapping conservativo in review obbligatoria.",
        )

    if prefix == "030":
        proc = _find_registry_match(("sfratto",), registry) or _find_registry_match(("locazione",), registry)
        if proc:
            return _procedure_to_candidate(
                xsd_code,
                proc,
                confidence_score=85,
                review_status="needs_review",
                notes="Prefisso 030 riconosciuto come sfratto/convalida; review obbligatoria.",
            )
        return _placeholder_candidate(
            xsd_code,
            "PROC_PCT_CONVALIDA_SFRATTO_NEEDS_REVIEW",
            confidence_score=80,
            workflow_code="WF_PCT_SFRATTO_CONVALIDA",
            notes="Prefisso 030 riconosciuto; procedura operativa puntuale non trovata nel registry.",
        )

    if prefix in CAUTELARI_PREFIXES:
        proc = _find_registry_match(("cautelar",), registry)
        if proc:
            return _procedure_to_candidate(
                xsd_code,
                proc,
                confidence_score=78,
                review_status="needs_review",
                notes=f"Prefisso {prefix} riconosciuto come cautelare; review obbligatoria.",
            )
        return _placeholder_candidate(
            xsd_code,
            "PROC_PCT_CAUTELARE_NEEDS_REVIEW",
            confidence_score=75,
            workflow_code="WF_PCT_CAUTELARE_REVIEW",
            notes=f"Prefisso {prefix} riconosciuto come cautelare; mapping generico needs_review.",
        )

    if prefix == "020":
        proc = _find_registry_match(("possessor",), registry)
        if proc:
            return _procedure_to_candidate(
                xsd_code,
                proc,
                confidence_score=78,
                review_status="needs_review",
                notes="Prefisso 020 riconosciuto come possessoria; review obbligatoria.",
            )
        return _placeholder_candidate(
            xsd_code,
            "PROC_PCT_POSSESSORIA_NEEDS_REVIEW",
            confidence_score=75,
            workflow_code="WF_PCT_POSSESSORIA_REVIEW",
            notes="Prefisso 020 riconosciuto come possessoria; mapping generico needs_review.",
        )

    return _placeholder_candidate(
        xsd_code,
        f"PROC_PCT_XSD_{prefix or 'UNKNOWN'}_NEEDS_REVIEW",
        confidence_score=25 if xsd_code or label else 10,
        workflow_code="WF_PCT_GENERICO_REVIEW",
        notes="Nessuna regola deterministica sufficiente: mapping pending, nessuna validazione automatica.",
    )


def apply_mapping(repo: ProcedureLifecycleRepository, candidate: MappingCandidate) -> int:
    return repo.upsert_xsd_mapping(candidate.to_row())


def map_all_xsd_objects(repo: ProcedureLifecycleRepository, dry_run: bool = True) -> MappingReport:
    if not dry_run:
        repo.ensure_extended_schema()
    xsd_objects = repo.list_xsd_objects(active_only=True)
    automatic = needs_review = validated = applied = 0
    for xsd_object in xsd_objects:
        candidate = infer_mapping_for_xsd(xsd_object)
        automatic += 1 if candidate.confidence_score >= 75 else 0
        needs_review += 1 if candidate.review_status == "needs_review" else 0
        validated += 1 if candidate.review_status == "validated" else 0
        if not dry_run:
            apply_mapping(repo, candidate)
            applied += 1
    return MappingReport(
        dry_run=dry_run,
        total_xsd_objects=len(xsd_objects),
        automatic_mappings=automatic,
        needs_review=needs_review,
        validated=validated,
        applied=applied,
    )
