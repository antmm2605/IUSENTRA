from __future__ import annotations

from datetime import timedelta
from typing import Any

from pct.daily_plan.clock import Clock, system_clock

from ..registry import WorkflowRecipe
from ._common import plan, readonly_step, write_step


def build(payload: dict[str, Any], *, clock: Clock | None = None):
    clock = clock or system_clock()
    fascicolo_id = str(payload.get("fascicolo_id") or "").strip()
    domani = (clock.today() + timedelta(days=1)).isoformat()
    steps = [
        readonly_step(
            "piano_del_giorno",
            "Legge il piano operativo del giorno (priorità, scadenze, copertura)",
            "daily_plan",
            {"limit": 25},
            minutes=16,
        ),
        readonly_step("fascicoli_aperti", "Legge fascicoli aperti e priorità", "fascicolo", {"query": "", "include_archiviati": False}, minutes=10),
        readonly_step("scadenze_14_giorni", "Verifica scadenze dei prossimi quattordici giorni (arretrati inclusi)", "scadenziario", {"giorni": 14, "solo_aperte": True}, minutes=8),
        readonly_step("agenda_14_giorni", "Verifica agenda dei prossimi quattordici giorni", "agenda", {"giorni": 14}, minutes=12),
        readonly_step(
            "comunicazioni_recenti",
            "Legge segnali operativi recenti",
            "operational_knowledge",
            {"question": "Individua comunicazioni, eventi e blocchi operativi recenti da presidiare oggi.", "max_items": 12},
            minutes=10,
        ),
        write_step(
            "task_prioritari",
            "Propone attività prioritarie per la giornata",
            "create_task",
            {
                "titolo": "Presidio priorità del giorno",
                "descrizione": "Attività proposta dalla regia agentica dopo lettura di fascicoli, agenda e scadenze.",
                "fascicolo_id": fascicolo_id,
                "priorita": "alta",
                "impatto": "Riduce il controllo manuale quotidiano e concentra l'avvocato sulle urgenze.",
            },
            minutes=18,
        ),
        write_step(
            "promemoria_urgenze",
            "Propone promemoria per scadenze imminenti",
            "create_deadline",
            {
                "titolo": "Verifica urgenze segnalate da Lex",
                "descrizione": "Promemoria da approvare per presidiare scadenze e appuntamenti critici.",
                "fascicolo_id": fascicolo_id,
                "data_scadenza": domani,
                "giorni_preavviso": [1],
                "impatto": "Evita che il controllo resti nella sola memoria dello studio.",
            },
            minutes=10,
            risk="low",
        ),
    ]
    return plan(
        workflow_code="triage_giornaliero",
        title="Triage giornaliero",
        description="Controlla fascicoli, scadenze, agenda e segnali recenti, poi prepara proposte operative.",
        steps=steps,
        baseline_minutes=84,
        expected_review_minutes=13,
        expected_correction_minutes=3,
        risk_level="medium",
        fascicolo_id=fascicolo_id,
        confidence=0.78,
    )


def recipe() -> WorkflowRecipe:
    return WorkflowRecipe(
        code="triage_giornaliero",
        title="Triage giornaliero",
        description="Presidio mattutino di fascicoli, scadenze, agenda e comunicazioni con proposte approvabili.",
        risk_level="medium",
        baseline_minutes=84,
        builder=build,
    )
