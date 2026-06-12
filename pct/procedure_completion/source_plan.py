"""Piano fonti multi-sorgente del Procedure Completion Engine.

Ordine governato: catalogo interno PST/XSD -> template atti -> riferimenti
ufficiali della famiglia XSD (pct/procedure_source_research) -> retriever
ufficiali (Normattiva/Gazzetta) e fonte fiscale solo se abilitati. Una fonte
disabilitata o insufficiente produce un gap dichiarato, mai un'invenzione.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Optional

from pct.procedure_completion.models import (
    ProcedureCompletionGap,
    ProcedureCompletionRequest,
    ProcedureCompletionSource,
)

PST_DOWNLOAD_PAGE = "https://pst.giustizia.it/PST/it/download.page"


@dataclass(slots=True)
class SourcePlanSettings:
    """Fonti esterne abilitabili; default fail-closed (solo layer interni)."""

    normattiva_enabled: bool = False
    gazzetta_enabled: bool = False
    agenzia_entrate_enabled: bool = False
    eurlex_enabled: bool = False
    # Retriever iniettabili per test/figure governate: callable(query) -> list[dict]
    normattiva_retriever: Optional[Callable[[str], list[dict[str, Any]]]] = None
    gazzetta_retriever: Optional[Callable[[str], list[dict[str, Any]]]] = None
    agenzia_entrate_retriever: Optional[Callable[[str], list[dict[str, Any]]]] = None


@dataclass(slots=True)
class SourcePlan:
    sources: list[ProcedureCompletionSource] = field(default_factory=list)
    gaps: list[ProcedureCompletionGap] = field(default_factory=list)
    evidence_rows: list[dict[str, Any]] = field(default_factory=list)
    catalog_entry: dict[str, Any] = field(default_factory=dict)
    xsd_object: dict[str, Any] = field(default_factory=dict)
    fiscal_rows: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": [src.to_dict() for src in self.sources],
            "gaps": [gap.to_dict() for gap in self.gaps],
            "catalog_entry": self.catalog_entry,
            "xsd_object": self.xsd_object,
        }


def _hash_fonte(*parts: str) -> str:
    base = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:24]


def _oggi() -> str:
    return date.today().isoformat()


def _fonte_catalogo_pst(entry: dict[str, Any]) -> ProcedureCompletionSource:
    return ProcedureCompletionSource(
        source_type="technical",
        title=f"Catalogo codici oggetto PST - {entry.get('codice')} {entry.get('descrizione', '')}".strip(),
        url=PST_DOWNLOAD_PAGE,
        authority="PST Giustizia - Ministero della Giustizia",
        trust_class="B",
        copyright_policy="metadata_only",
        origin="catalogo_pst",
        source_hash=_hash_fonte("catalogo_pst", str(entry.get("codice"))),
        last_checked_at=_oggi(),
    )


def _fonte_da_reference(row: dict[str, Any]) -> ProcedureCompletionSource:
    tipo = str(row.get("source_type") or "official")
    if tipo not in {"official", "technical", "jurisprudence", "professional", "internal"}:
        tipo = "official" if tipo in {"normattiva", "gazzetta"} else "technical"
    return ProcedureCompletionSource(
        source_type=tipo,
        title=str(row.get("source_title") or row.get("title") or ""),
        url=str(row.get("source_url") or row.get("url") or ""),
        authority=str(row.get("authority") or ""),
        trust_class="A" if tipo == "official" else ("B" if tipo == "technical" else ""),
        copyright_policy=str(row.get("copyright_policy") or ("summary_only" if tipo == "professional" else "metadata_only")),
        excerpt=str(row.get("extracted_principle") or row.get("excerpt") or "")[:500],
        origin=str(row.get("origin") or "xsd"),
        source_hash=_hash_fonte(tipo, str(row.get("source_url") or row.get("url") or ""), str(row.get("source_title") or "")),
        last_checked_at=str(row.get("last_checked_at") or _oggi()),
    )


def _gap(codice: str, descrizione: str, severita: str = "warning", azione: str = "") -> ProcedureCompletionGap:
    return ProcedureCompletionGap(
        codice_gap=codice,
        descrizione=descrizione,
        severita=severita,
        azione_suggerita=azione,
    )


def _xsd_object_per_codice(codice: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Oggetto XSD minimo per il planner della pipeline procedurale esistente."""
    return {
        "xsd_code": codice,
        "xsd_label": str(entry.get("descrizione") or entry.get("label") or ""),
        "family_label": str(entry.get("parent_label") or ""),
        "area_label": str(entry.get("area_label") or entry.get("area") or ""),
        "registri": entry.get("registri") or "",
        "file_fonte": str(entry.get("file_fonte") or ""),
    }


def build_source_plan(
    request: ProcedureCompletionRequest,
    *,
    settings: SourcePlanSettings | None = None,
    catalog_lookup: Optional[Callable[[str], Optional[dict[str, Any]]]] = None,
    lifecycle_evidence_loader: Optional[Callable[[str, str], list[dict[str, Any]]]] = None,
) -> SourcePlan:
    settings = settings or SourcePlanSettings()
    plan = SourcePlan()

    # 1) Catalogo interno PST (codici oggetto ministeriali) - layer tecnico.
    if catalog_lookup is None:
        from pct.pratiche_collegate_catalog import codice_oggetto_pst_entry as catalog_lookup  # type: ignore[assignment]
    entry = catalog_lookup(request.codice) if request.codice else None
    if entry:
        plan.catalog_entry = dict(entry)
        plan.sources.append(_fonte_catalogo_pst(entry))
        plan.xsd_object = _xsd_object_per_codice(request.codice, entry)
    else:
        plan.gaps.append(
            _gap(
                "codice_non_in_catalogo",
                "Codice non trovato nel catalogo ministeriale/template: la scheda resta da verificare.",
                severita="blocking",
                azione="Verificare il codice oggetto sul catalogo PST aggiornato o correggere l'input.",
            )
        )

    # 2) Riferimenti ufficiali per famiglia XSD (pipeline procedurale esistente).
    if plan.xsd_object:
        try:
            from pct.procedure_source_research import build_source_plan_for_xsd

            ricerca = build_source_plan_for_xsd(plan.xsd_object, request.codice)
            for riferimento in ricerca.references:
                row = riferimento.to_evidence(request.codice, request.codice)
                plan.evidence_rows.append(row)
                plan.sources.append(_fonte_da_reference(row))
        except Exception:
            plan.gaps.append(
                _gap(
                    "fonti_famiglia_xsd_non_disponibili",
                    "Riferimenti ufficiali della famiglia XSD non disponibili dal runtime corrente.",
                    severita="warning",
                    azione="Eseguire la Procedure Lifecycle Knowledge Pipeline per popolare le evidenze.",
                )
            )

    # 3) Evidenze gia' censite nella knowledge pipeline (riuso, niente rete).
    if lifecycle_evidence_loader is not None and request.codice:
        try:
            for row in lifecycle_evidence_loader(request.codice, request.codice) or []:
                plan.evidence_rows.append(dict(row))
                plan.sources.append(_fonte_da_reference(dict(row)))
        except Exception:
            plan.gaps.append(
                _gap(
                    "evidenze_lifecycle_non_lette",
                    "Evidenze della knowledge pipeline non leggibili dal runtime corrente.",
                    severita="info",
                )
            )

    # 4) Retriever ufficiali esterni: solo se abilitati e configurati.
    query = request.denominazione or request.codice
    if settings.normattiva_enabled and settings.normattiva_retriever is not None:
        try:
            for row in settings.normattiva_retriever(query) or []:
                row = dict(row)
                row.setdefault("source_type", "official")
                row.setdefault("origin", "normattiva")
                plan.evidence_rows.append(row)
                plan.sources.append(_fonte_da_reference(row))
        except Exception:
            plan.gaps.append(_gap("normattiva_non_raggiungibile", "Normattiva configurata ma non raggiungibile.", "warning"))
    else:
        plan.gaps.append(
            _gap(
                "normattiva_non_abilitata",
                "Retriever Normattiva non abilitato: verifica di vigenza da completare in revisione.",
                severita="info",
                azione="Abilitare il Centro Fonti Ufficiali (import Normattiva) per la verifica testuale.",
            )
        )
    if settings.gazzetta_enabled and settings.gazzetta_retriever is not None:
        try:
            for row in settings.gazzetta_retriever(query) or []:
                row = dict(row)
                row.setdefault("source_type", "official")
                row.setdefault("origin", "gazzetta")
                plan.evidence_rows.append(row)
                plan.sources.append(_fonte_da_reference(row))
        except Exception:
            plan.gaps.append(_gap("gazzetta_non_raggiungibile", "Gazzetta Ufficiale configurata ma non raggiungibile.", "warning"))

    # 5) Adempimenti fiscali: solo da fonte fiscale configurata (Agenzia Entrate).
    if settings.agenzia_entrate_enabled and settings.agenzia_entrate_retriever is not None:
        try:
            for row in settings.agenzia_entrate_retriever(query) or []:
                row = dict(row)
                row.setdefault("source_type", "technical")
                row.setdefault("origin", "agenzia_entrate")
                plan.fiscal_rows.append(row)
                plan.sources.append(_fonte_da_reference(row))
        except Exception:
            plan.gaps.append(_gap("agenzia_entrate_non_raggiungibile", "Fonte Agenzia Entrate configurata ma non raggiungibile.", "warning"))
    else:
        plan.gaps.append(
            _gap(
                "adempimenti_fiscali_senza_fonte",
                "Adempimenti fiscali non determinabili: fonte Agenzia Entrate non configurata.",
                severita="warning",
                azione="Configurare la fonte fiscale governata o completare in revisione avvocato.",
            )
        )

    return plan


__all__ = ["SourcePlan", "SourcePlanSettings", "build_source_plan", "PST_DOWNLOAD_PAGE"]
