"""Pipeline SQL della catalogazione dei documenti già presenti nel fascicolo."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .catalog_resolver import (
    REGISTRY_VERSION,
    RESOLVER_VERSION,
    PROFILE_SOURCES,
    infer_fascicolo_context_from_document_corpus,
    profile_source_rows,
    resolve_profile,
    resolve_document_catalog,
)
from .models import DocumentCatalogAssignment, new_id, utc_now
from .repository import DocumentAIRepository
from .sources import DocumentAISource


@dataclass(slots=True)
class CatalogPipelineResult:
    total_sources: int = 0
    queued: int = 0
    processed: int = 0
    proposed: int = 0
    review_required: int = 0
    skipped_current: int = 0
    waiting_for_index: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sources": self.total_sources,
            "queued": self.queued,
            "processed": self.processed,
            "proposed": self.proposed,
            "review_required": self.review_required,
            "skipped_current": self.skipped_current,
            "waiting_for_index": self.waiting_for_index,
            "errors": list(self.errors),
        }


class FascicoloDocumentCatalogPipeline:
    """Processa solo la lista esplicita di documenti del fascicolo.

    Non esegue ricerche su disco, non scarica fonti e non può promuovere il
    mirror JSON a fonte dei risultati. L'estrazione viene prima da Document AI.
    """

    def __init__(self, repository: DocumentAIRepository) -> None:
        self.repository = repository

    def ensure_rule_inventory(self, tenant_id: str) -> str:
        rule_set_id = self.repository.ensure_catalog_rule_set(
            tenant_id=tenant_id,
            resolver_version=RESOLVER_VERSION,
            registry_version=REGISTRY_VERSION,
            description="Catalogazione documentale fascicolo: profili e fonti ufficiali versionate.",
        )
        existing = {
            (str(item.get("profile_id") or ""), str(item.get("source_id") or "")): item
            for item in self.repository.list_catalog_source_snapshots(tenant_id, rule_set_id)
        }
        for profile_id in PROFILE_SOURCES:
            for source in profile_source_rows(profile_id):
                source_id = str(source["id"])
                source_metadata = {
                    "source_type": source.get("source_type"),
                    "registry_version": REGISTRY_VERSION,
                }
                snapshot_sha256 = str(source.get("snapshot_sha256") or "") or None
                last_verified_at = str(source.get("last_verified_at") or "") or None
                current = existing.get((profile_id, source_id))
                if current and _source_snapshot_matches(
                    current,
                    official_url=str(source["official_url"]),
                    verification_status=str(source["verification_status"]),
                    snapshot_sha256=snapshot_sha256,
                    last_verified_at=last_verified_at,
                    source_metadata=source_metadata,
                ):
                    continue
                self.repository.upsert_catalog_source_snapshot(
                    tenant_id=tenant_id,
                    rule_set_id=rule_set_id,
                    profile_id=profile_id,
                    source_id=source_id,
                    official_url=str(source["official_url"]),
                    verification_status=str(source["verification_status"]),
                    snapshot_sha256=snapshot_sha256,
                    last_verified_at=last_verified_at,
                    source_metadata=source_metadata,
                )
        return rule_set_id

    def run(
        self,
        *,
        tenant_id: str,
        fascicolo: Any,
        sources: Iterable[DocumentAISource],
        actor: str,
        process: bool,
        retry: bool = False,
    ) -> CatalogPipelineResult:
        with self.repository.catalog_write_batch():
            return self._run(
                tenant_id=tenant_id,
                fascicolo=fascicolo,
                sources=sources,
                actor=actor,
                process=process,
                retry=retry,
            )

    def _run(
        self,
        *,
        tenant_id: str,
        fascicolo: Any,
        sources: Iterable[DocumentAISource],
        actor: str,
        process: bool,
        retry: bool = False,
    ) -> CatalogPipelineResult:
        fid = str(getattr(fascicolo, "id", "") or "").strip()
        if not fid:
            raise ValueError("Fascicolo non disponibile per la catalogazione.")
        rule_set_id = self.ensure_rule_inventory(tenant_id)
        result = CatalogPipelineResult()
        document_sources = [source for source in sources if str(source.fascicolo_id or "") == fid]
        result.total_sources = len(document_sources)
        records = self.repository.list_documents(tenant_id, fid)
        records_by_sha: dict[str, Any] = {}
        for record in records:
            sha = str(getattr(record, "sha256", "") or "")
            if sha and str(getattr(record, "status", "") or "") == "ready":
                records_by_sha[sha] = record
        existing_assignments = {
            (str(item.document_id or ""), str(item.document_sha256 or "")): item
            for item in self.repository.list_catalog_assignments(tenant_id, fid, include_superseded=True)
        }
        open_review_assignment_ids = {
            str(review.assignment_id or "")
            for review in self.repository.list_catalog_reviews(tenant_id, fid)
        }
        context = _fascicolo_context(fascicolo)
        extracted_by_record_id: dict[str, str] = {}
        profile_id, _ = resolve_profile(context)
        if not profile_id:
            corpus: list[dict[str, str]] = []
            for source in document_sources:
                record = records_by_sha.get(str(source.sha256 or ""))
                if record is None:
                    continue
                record_id = str(getattr(record, "id", "") or "")
                if not record_id:
                    continue
                extracted = self.repository.get_extracted_text(
                    tenant_id,
                    fid,
                    record_id,
                    str(getattr(record, "current_version_id", "") or "") or None,
                )
                text = str(getattr(extracted, "text", "") or "")
                extracted_by_record_id[record_id] = text
                corpus.append({
                    "document_id": str(source.source_id or source.metadata.get("documento_id") or ""),
                    "filename": source.filename,
                    "text": text,
                })
            context = infer_fascicolo_context_from_document_corpus(context, corpus)
        for source in document_sources:
            document_id = str(source.source_id or source.metadata.get("documento_id") or "").strip()
            if not document_id:
                result.errors.append(f"{source.filename}: identificativo documento assente.")
                continue
            record = records_by_sha.get(str(source.sha256 or ""))
            if record is None:
                result.waiting_for_index += 1
                continue
            existing = existing_assignments.get((document_id, str(source.sha256 or "")))
            if existing and str(existing.source_state or "") == "manual_override":
                # La correzione dell'avvocato è prevalente anche dopo un
                # aggiornamento del resolver: il nuovo motore non può
                # sovrascrivere un esito umano già tracciato nel fascicolo.
                result.skipped_current += 1
                continue
            if existing and existing.resolver_version == RESOLVER_VERSION and not retry:
                # Una revisione aperta è già la risposta governata per il
                # documento: non la rigeneriamo e non rieseguiamo estrazione
                # o resolver. Se l'avvocato l'ha chiusa mantenendo "da
                # verificare", la prossima esecuzione deve invece poter
                # riaprire un nuovo ciclo tracciabile.
                has_open_review = str(existing.id or "") in open_review_assignment_ids
                if existing.status != "review_required" or has_open_review:
                    result.skipped_current += 1
                    continue
            # La lettura del catalogo è un'operazione strettamente read-only:
            # non deve creare code che nessun worker consumerà, né far
            # apparire un aggiornamento inesistente. Il job SQL nasce solo dal
            # comando esplicito che richiede anche l'elaborazione.
            if not process:
                continue
            job = self.repository.queue_catalog_job(
                tenant_id=tenant_id,
                fascicolo_id=fid,
                document_id=document_id,
                document_ai_id=str(getattr(record, "id", "") or "") or None,
                document_version_id=str(getattr(record, "current_version_id", "") or "") or None,
                document_sha256=str(source.sha256 or getattr(record, "sha256", "") or ""),
                resolver_version=RESOLVER_VERSION,
                requested_by=actor,
                retry=retry,
            )
            result.queued += 1
            self._process_source(
                tenant_id=tenant_id,
                fascicolo_id=fid,
                source=source,
                record=record,
                context=context,
                actor=actor,
                rule_set_id=rule_set_id,
                job_id=str(job["id"]),
                result=result,
                extracted_text=extracted_by_record_id.get(str(getattr(record, "id", "") or "")),
            )
        return result
    def _process_source(
        self,
        *,
        tenant_id: str,
        fascicolo_id: str,
        source: DocumentAISource,
        record: Any,
        context: dict[str, Any],
        actor: str,
        rule_set_id: str,
        job_id: str,
        result: CatalogPipelineResult,
        extracted_text: str | None = None,
    ) -> None:
        self.repository.mark_catalog_job(tenant_id=tenant_id, job_id=job_id, status="processing")
        document_id = str(source.source_id or source.metadata.get("documento_id") or "").strip()
        try:
            if extracted_text is None:
                extracted = self.repository.get_extracted_text(
                    tenant_id, fascicolo_id, str(getattr(record, "id", "") or ""), str(getattr(record, "current_version_id", "") or "") or None
                )
                text = str(getattr(extracted, "text", "") or "")
            else:
                text = extracted_text
            resolution = resolve_document_catalog(
                tenant_id=tenant_id,
                fascicolo_id=fascicolo_id,
                document_id=document_id,
                document_sha256=str(source.sha256 or getattr(record, "sha256", "") or ""),
                filename=source.filename,
                extracted_text=text,
                document_metadata=dict(source.metadata or {}),
                fascicolo_context=context,
            )
            now = utc_now()
            assignment = DocumentCatalogAssignment(
                id=new_id("catalog-assignment"), tenant_id=tenant_id, fascicolo_id=fascicolo_id,
                document_id=document_id, document_ai_id=str(getattr(record, "id", "") or "") or None,
                document_version_id=str(getattr(record, "current_version_id", "") or "") or None,
                document_sha256=str(source.sha256 or getattr(record, "sha256", "") or ""),
                profile_id=resolution.profile_id, legal_area=resolution.legal_area or None,
                legal_branch=resolution.legal_branch or None, legal_subfamily=resolution.legal_subfamily or None,
                jurisdiction=resolution.jurisdiction or None, rite=resolution.rite or None,
                proceeding_phase=resolution.proceeding_phase or None, document_nature=resolution.document_nature,
                document_label=resolution.document_label, document_section=resolution.document_section,
                deposit_role=resolution.deposit_role, deposit_candidate=resolution.deposit_candidate,
                status=resolution.status, confidence=resolution.confidence, source_state=resolution.source_state,
                resolver_version=RESOLVER_VERSION, rule_set_id=rule_set_id, reason=resolution.reason,
                metadata={
                    "filename": source.filename,
                    "source_type": source.source_type,
                    "document_ai_status": str(getattr(record, "status", "") or ""),
                    "legal_source_count": len(profile_source_rows(resolution.profile_id or "")),
                    "profile_inferred_from_content": bool(context.get("_profile_inference_reason")),
                    "profile_inference_documents": list(context.get("_profile_evidence_documents") or [])[:5],
                },
                created_by=actor, created_at=now, updated_by=actor, updated_at=now,
            )
            self.repository.save_catalog_assignment(
                assignment, candidates=resolution.candidates, evidence=resolution.evidence, review=resolution.review
            )
            self.repository.append_audit_event({
                "id": new_id("catalog-audit"), "tenant_id": tenant_id, "fascicolo_id": fascicolo_id,
                "document_id": document_id, "version_id": assignment.document_version_id, "user_id": actor,
                "event_type": "document_catalog.classified", "timestamp": now, "sha256": assignment.document_sha256,
                "filename": source.filename, "status": assignment.status,
                "payload": {"profile_id": assignment.profile_id, "confidence": assignment.confidence, "source_state": assignment.source_state},
            })
            self.repository.mark_catalog_job(
                tenant_id=tenant_id, job_id=job_id,
                status="review_required" if assignment.status == "review_required" else "completed",
            )
            result.processed += 1
            if assignment.status == "review_required":
                result.review_required += 1
            else:
                result.proposed += 1
        except Exception as exc:
            self.repository.mark_catalog_job(
                tenant_id=tenant_id, job_id=job_id, status="error", error_code="catalog_pipeline_error", error_message=str(exc)[:500]
            )
            result.errors.append(f"{source.filename}: catalogazione non completata ({exc}).")


def _source_snapshot_matches(
    current: dict[str, Any],
    *,
    official_url: str,
    verification_status: str,
    snapshot_sha256: str | None,
    last_verified_at: str | None,
    source_metadata: dict[str, Any],
) -> bool:
    import json

    return (
        str(current.get("official_url") or "") == official_url
        and str(current.get("verification_status") or "") == verification_status
        and (current.get("snapshot_sha256") or None) == (snapshot_sha256 or None)
        and (current.get("last_verified_at") or None) == (last_verified_at or None)
        and str(current.get("source_metadata_json") or "") == json.dumps(source_metadata, ensure_ascii=False)
    )


def _fascicolo_context(fascicolo: Any) -> dict[str, Any]:
    profile = getattr(fascicolo, "profilo_deposito", {}) or {}
    profile = dict(profile) if isinstance(profile, dict) else {}
    return {
        "area": profile.get("area") or profile.get("area_pratica") or getattr(fascicolo, "area_pratica", ""),
        "branca": profile.get("branca") or profile.get("branch") or profile.get("materia") or "",
        "sottobranca": profile.get("sottobranca") or profile.get("subfamily") or profile.get("sottomateria") or "",
        "giurisdizione": profile.get("giurisdizione") or getattr(fascicolo, "tribunale", ""),
        "rito": profile.get("rito") or getattr(fascicolo, "tipo_procedimento", ""),
        "fase": profile.get("fase") or "",
        "canale": profile.get("canale_telematico") or getattr(fascicolo, "canale_operativo", "") or getattr(fascicolo, "source", ""),
        "source": getattr(fascicolo, "source", ""),
    }


__all__ = ["CatalogPipelineResult", "FascicoloDocumentCatalogPipeline"]
