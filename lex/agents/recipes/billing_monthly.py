from __future__ import annotations

from typing import Any

from ..registry import WorkflowRecipe
from ._common import plan, readonly_step, text, write_step


def build(payload: dict[str, Any]):
    fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
    cliente_id = text(payload, "cliente_id")
    descrizione = text(payload, "descrizione", "Attività ricostruita da agenda e fascicolo")
    steps = [
        readonly_step("fascicoli_economici", "Legge fascicoli collegati alla valorizzazione", "fascicolo", {"query": "", "section": "attivita"}, minutes=18),
        readonly_step("agenda_mese", "Legge appuntamenti e udienze del mese", "agenda", {"giorni": 31}, minutes=16),
        readonly_step("preventivi_conferimenti", "Legge preventivi e conferimenti disponibili", "preventivi", {"fascicolo_id": fascicolo_id}, minutes=10),
        write_step(
            "timesheet_proposto",
            "Propone voce timesheet",
            "create_timesheet_entry",
            {
                "descrizione": descrizione,
                "minuti": int(payload.get("params", {}).get("minuti") or 60),
                "fascicolo_id": fascicolo_id,
                "cliente_id": cliente_id,
                "origine": "Regia Agentica Studio",
                "impatto": "Trasforma attività già emerse in consuntivo da verificare.",
            },
            minutes=20,
            risk="low",
        ),
        write_step(
            "parcella_bozza",
            "Propone parcella in bozza",
            "create_invoice_draft",
            {
                "cliente_id": cliente_id,
                "fascicolo_id": fascicolo_id,
                "descrizione": descrizione,
                "importo": float(payload.get("params", {}).get("importo") or 0.0),
                "impatto": "Prepara una parcella non definitiva da controllare prima dell'emissione.",
            },
            minutes=45,
            risk="medium",
        ),
    ]
    return plan(
        workflow_code="billing_monthly",
        title="Consuntivo mensile",
        description="Raccoglie attività, prepara timesheet e parcelle in bozza senza emissione automatica.",
        steps=steps,
        baseline_minutes=95,
        expected_review_minutes=14,
        expected_correction_minutes=5,
        risk_level="medium",
        fascicolo_id=fascicolo_id,
        confidence=0.72,
    )


def recipe() -> WorkflowRecipe:
    return WorkflowRecipe(
        code="billing_monthly",
        title="Consuntivo mensile",
        description="Valorizza attività e prepara bozze economiche da approvare.",
        risk_level="medium",
        baseline_minutes=95,
        builder=build,
    )
