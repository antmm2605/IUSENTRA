from __future__ import annotations

from typing import Any

from ..registry import WorkflowRecipe
from ._common import plan, readonly_step, write_step


def build(payload: dict[str, Any]):
    fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
    warnings = [] if fascicolo_id else ["Seleziona il fascicolo prima di approvare correzioni pre-deposito."]
    steps = [
        readonly_step("documenti_fascicolo", "Legge documenti del fascicolo", "list_fascicolo_documents", {"fascicolo_id": fascicolo_id}, minutes=20),
        readonly_step("stato_telematico", "Legge checklist e ricevute disponibili", "telematico", {"fascicolo_id": fascicolo_id, "sezione": "checklist"}, minutes=20),
        readonly_step("contesto_deposito", "Raccoglie contesto utile al controllo deposito", "collect_fascicolo_context", {"fascicolo_id": fascicolo_id}, minutes=18),
        write_step(
            "correzioni_checklist",
            "Propone aggiornamento checklist deposito",
            "update_checklist",
            {
                "fascicolo_id": fascicolo_id,
                "titolo": "Correzioni pre-deposito",
                "items": ["atto principale presente", "allegati verificati", "ricevute lette", "anomalie da correggere"],
                "impatto": "Trasforma le anomalie in controlli tracciati senza depositare l'atto.",
            },
            minutes=22,
            risk="medium",
        ),
        write_step(
            "task_anomalie",
            "Propone attività di correzione anomalie",
            "create_task",
            {
                "titolo": "Correggere anomalie pre-deposito",
                "descrizione": "Attività da approvare dopo controllo documenti, checklist e ricevute disponibili.",
                "fascicolo_id": fascicolo_id,
                "priorita": "alta",
                "impatto": "Riduce il tempo di interpretazione ripetitiva prima del deposito.",
            },
            minutes=15,
            risk="low",
        ),
    ]
    return plan(
        workflow_code="predeposito",
        title="Pre-deposito",
        description="Controlla documenti, checklist e ricevute; propone correzioni senza deposito automatico.",
        steps=steps,
        baseline_minutes=95,
        expected_review_minutes=14,
        expected_correction_minutes=4,
        risk_level="high",
        fascicolo_id=fascicolo_id,
        confidence=0.76,
        warnings=warnings,
    )


def recipe() -> WorkflowRecipe:
    return WorkflowRecipe(
        code="predeposito",
        title="Pre-deposito",
        description="Verifica ripetitiva di atto principale, allegati, checklist, ricevute e anomalie.",
        risk_level="high",
        baseline_minutes=95,
        builder=build,
    )

