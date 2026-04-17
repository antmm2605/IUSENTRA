"""Assistente di migrazione iniziale per clienti, fascicoli e dati core."""

from __future__ import annotations

from typing import Any

from pct.checklist_atti import TUTTI_I_TEMPLATE
from pct.product_governance import build_migration_program_payload, build_storage_parity_payload
from web.services.admin_surfaces_shared import (
    count_documents,
    get_agenda_manager,
    get_clienti_manager,
    get_fascicoli_manager,
    get_scadenziario_manager,
    get_template_manager,
)


def build_migration_assistant() -> dict[str, Any]:
    clienti = get_clienti_manager()
    fascicoli = get_fascicoli_manager()
    agenda = get_agenda_manager()
    scadenziario = get_scadenziario_manager()
    template_manager = get_template_manager()

    clienti_totale = int(clienti.statistiche().get("totale", 0) or 0)
    fascicoli_totale = int(fascicoli.statistiche().get("totale", 0) or 0)
    agenda_totale = int(agenda.statistiche().get("totale", 0) or 0)
    scadenze_totale = int(scadenziario.statistiche().get("totale", 0) or 0)
    documenti_totale = int(count_documents(fascicoli) or 0)
    template_totale = len(template_manager.tutti())

    modules = [
        {
            "title": "Clienti",
            "count": clienti_totale,
            "status": "ok" if clienti_totale else "warning",
            "next_step": "Verificare anagrafica, codici fiscali, PEC e soggetti collegati.",
        },
        {
            "title": "Fascicoli",
            "count": fascicoli_totale,
            "status": "ok" if fascicoli_totale else "warning",
            "next_step": "Allineare numero RG, tribunale, controparte e pratica attiva.",
        },
        {
            "title": "Appuntamenti",
            "count": agenda_totale,
            "status": "ok" if agenda_totale else "warning",
            "next_step": "Importare udienze, riunioni e reminder della prima settimana.",
        },
        {
            "title": "Scadenze",
            "count": scadenze_totale,
            "status": "ok" if scadenze_totale else "warning",
            "next_step": "Presidiare termini perentori e scadenze operative collegate.",
        },
        {
            "title": "Documenti",
            "count": documenti_totale,
            "status": "ok" if documenti_totale else "warning",
            "next_step": "Indicizzare PDF, DOCX e firmati .p7m dei fascicoli prioritari.",
        },
        {
            "title": "Template base",
            "count": template_totale,
            "status": "ok" if template_totale else "warning",
            "next_step": "Mappare i modelli interni piu' usati e le clausole ricorrenti.",
        },
    ]

    workflow = [
        "1. Caricare clienti e soggetti essenziali.",
        "2. Importare fascicoli aperti e documenti chiave.",
        "3. Sincronizzare agenda, udienze e scadenziario.",
        "4. Validare PEC, firma e canali telematici.",
        "5. Attivare Lex sui fascicoli prioritari e sulla regia giornaliera.",
    ]

    migration_program = build_migration_program_payload()
    storage_parity = build_storage_parity_payload()

    return {
        "modules": modules,
        "workflow": workflow,
        "built_in_templates": len(TUTTI_I_TEMPLATE),
        "migration_program": migration_program,
        "storage_parity": storage_parity["summary"],
    }
