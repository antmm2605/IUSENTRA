from __future__ import annotations

from typing import Any

from ..registry import WorkflowRecipe
from ._common import plan, readonly_step, text, write_step


def build(payload: dict[str, Any]):
    fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
    tipo_atto = text(payload, "tipo_atto", "bozza atto")
    template_id = text(payload, "template_id")
    warnings = []
    if not fascicolo_id:
        warnings.append("Seleziona un fascicolo prima di approvare la bozza documento.")
    steps = [
        readonly_step("template_disponibili", "Seleziona template atti disponibili", "list_template_atti", {"tipo": tipo_atto}, minutes=15),
        readonly_step("contesto_fascicolo", "Raccoglie contesto fascicolo senza inventare dati", "collect_fascicolo_context", {"fascicolo_id": fascicolo_id}, minutes=35),
        write_step(
            "bozza_documento",
            "Propone bozza documento in editor",
            "create_document_draft",
            {
                "fascicolo_id": fascicolo_id,
                "tipo_atto": tipo_atto,
                "template_id": template_id,
                "titolo": f"Bozza {tipo_atto}".strip(),
                "campi_da_verificare": ["parti", "date", "procura", "allegati"],
                "impatto": "Prepara una prima bozza da controllare nell'editor senza inventare dati mancanti.",
            },
            minutes=70,
            risk="medium",
        ),
    ]
    return plan(
        workflow_code="redazione_atto",
        title="Redazione atto",
        description="Prepara una bozza professionale partendo da template e contesto fascicolo.",
        steps=steps,
        baseline_minutes=120,
        expected_review_minutes=18,
        expected_correction_minutes=6,
        risk_level="medium",
        fascicolo_id=fascicolo_id,
        confidence=0.74,
        warnings=warnings,
    )


def recipe() -> WorkflowRecipe:
    return WorkflowRecipe(
        code="redazione_atto",
        title="Redazione atto",
        description="Raccoglie template, contesto fascicolo e campi mancanti; crea bozze solo dopo approvazione.",
        risk_level="medium",
        baseline_minutes=120,
        builder=build,
    )

