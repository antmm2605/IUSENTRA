from __future__ import annotations

from typing import Any

from ..registry import WorkflowRecipe
from ._common import plan, readonly_step, text, write_step


def build(payload: dict[str, Any]):
    fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
    query = text(payload, "query", text(payload, "input_text", "ricerca preliminare"))
    steps = [
        readonly_step("fonti_interne", "Consulta fonti interne governate", "legal_intelligence", {"query": query, "fascicolo_id": fascicolo_id}, minutes=25),
        readonly_step("giurisprudenza", "Consulta archivio giurisprudenza disponibile", "giurisprudenza", {"query": query}, minutes=25),
        readonly_step(
            "conoscenza_operativa",
            "Collega conoscenza operativa senza usare fonti esterne con dati cliente",
            "operational_knowledge",
            {"question": query, "fascicolo_id": fascicolo_id, "source_mode": "governed"},
            minutes=15,
        ),
        write_step(
            "memo_ricerca",
            "Propone memo di ricerca preliminare",
            "create_document_draft",
            {
                "fascicolo_id": fascicolo_id,
                "tipo_atto": "memo ricerca",
                "titolo": "Memo ricerca preliminare",
                "query": query,
                "campi_da_verificare": ["fonti", "orientamenti", "lacune", "applicabilità al fascicolo"],
                "impatto": "Prepara il memo con fonti, confidenza e lacune per la valutazione professionale finale.",
            },
            minutes=45,
            risk="medium",
        ),
    ]
    return plan(
        workflow_code="legal_research",
        title="Ricerca preliminare",
        description="Raccoglie fonti interne e giurisprudenza, segnala confidenza e lacune, propone un memo.",
        steps=steps,
        baseline_minutes=110,
        expected_review_minutes=17,
        expected_correction_minutes=5,
        risk_level="medium",
        fascicolo_id=fascicolo_id,
        confidence=0.71,
    )


def recipe() -> WorkflowRecipe:
    return WorkflowRecipe(
        code="legal_research",
        title="Ricerca preliminare",
        description="Ricerca governata su fonti interne e archivio giurisprudenza, senza invio di dati fascicolo a canali esterni.",
        risk_level="medium",
        baseline_minutes=110,
        builder=build,
    )
