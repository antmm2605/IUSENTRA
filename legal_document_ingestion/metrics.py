"""Report metriche per la piattaforma Legal Document Understanding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .repository import LegalDocumentRepository


def build_legal_document_understanding_report(
    *,
    db_path: str | Path,
    storage_root: str | Path | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    root = Path(storage_root) if storage_root else Path(db_path).resolve().parent / "evidence"
    repository = LegalDocumentRepository(db_path, root)
    metrics = repository.metrics(tenant_id)
    report = {
        "report": "legal_document_understanding",
        "tenant_id": tenant_id,
        "ocr_cer": None,
        "ocr_wer": None,
        "field_accuracy": None,
        "classification_accuracy": metrics.get("classification_confidence_avg"),
        "entity_extraction_accuracy": None,
        "event_extraction_accuracy": metrics.get("event_extraction_accuracy"),
        "fascicolo_matching_accuracy": metrics.get("case_matching_confidence_avg"),
        "percentuale_documenti_auto_validati": metrics.get("auto_validated_percent"),
        "percentuale_documenti_in_review": metrics.get("review_percent"),
        "tempo_medio_revisione": None,
        "percentuale_riduzione_lavoro_studio_stimata": metrics.get("estimated_work_reduction_percent"),
        "errori_per_tipologia_documento": {},
        "errori_per_fonte": {},
        "target_80_percent_raggiunto": bool(metrics.get("target_80_percent_achieved")),
        "nota_misurazione": metrics.get("measurement_note"),
        "dataset": metrics,
    }
    if not metrics.get("documents"):
        report["target_80_percent_raggiunto"] = False
        report["nota_misurazione"] = "Nessun documento reale misurato: l'obiettivo 80% non può essere dichiarato raggiunto."
    return report
