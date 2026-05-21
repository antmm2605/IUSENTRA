from __future__ import annotations

from typing import Any

from ..registry import WorkflowRecipe
from ._common import plan, readonly_step, text, write_step


def build(payload: dict[str, Any]):
    input_text = text(payload, "input_text")
    nome = text(payload, "nome")
    cognome = text(payload, "cognome")
    ragione_sociale = text(payload, "ragione_sociale")
    oggetto = text(payload, "oggetto", input_text[:180] or "Nuovo incarico")
    warnings = []
    if not (nome or cognome or ragione_sociale or input_text):
        warnings.append("Dati cliente insufficienti: la proposta resta bloccabile in revisione.")
    steps = [
        readonly_step("ricerca_conflitti", "Controlla possibili conflitti su anagrafiche e fascicoli", "fascicolo", {"query": input_text or oggetto}, minutes=25),
        readonly_step("conferimenti", "Legge preventivi e conferimenti collegabili", "preventivi", {"query": input_text or oggetto}, minutes=12),
        write_step(
            "cliente_potenziale",
            "Propone cliente potenziale",
            "create_client_draft",
            {
                "tipo": "PERSONA_GIURIDICA" if ragione_sociale else "PERSONA_FISICA",
                "nome": nome,
                "cognome": cognome,
                "ragione_sociale": ragione_sociale,
                "codice_fiscale": text(payload, "codice_fiscale"),
                "partita_iva": text(payload, "partita_iva"),
                "note": oggetto,
                "impatto": "Evita reinserimento manuale dei dati già ricevuti.",
            },
            minutes=22,
            risk="medium",
        ),
        write_step(
            "fascicolo_draft",
            "Propone fascicolo in bozza",
            "create_fascicolo_draft",
            {
                "titolo": oggetto,
                "tipo": text(payload, "tipo_fascicolo", "ALTRO"),
                "nome_cliente": " ".join(part for part in (nome, cognome, ragione_sociale) if part).strip(),
                "oggetto": oggetto,
                "impatto": "Apre la pratica solo dopo controllo conflitto e approvazione.",
            },
            minutes=25,
            risk="medium",
        ),
        write_step(
            "checklist_documentale",
            "Propone checklist documentale iniziale",
            "update_checklist",
            {
                "fascicolo_id": "",
                "titolo": "Checklist nuovo incarico",
                "items": ["documento identità", "codice fiscale", "procura", "preventivo", "conferimento incarico"],
                "impatto": "Rende visibili i documenti mancanti prima dell'apertura operativa.",
            },
            minutes=12,
            risk="low",
        ),
    ]
    return plan(
        workflow_code="nuovo_incarico",
        title="Nuovo incarico",
        description="Estrae dati iniziali, controlla conflitti e propone cliente, fascicolo e checklist.",
        steps=steps,
        baseline_minutes=90,
        expected_review_minutes=14,
        expected_correction_minutes=4,
        risk_level="medium",
        confidence=0.73,
        warnings=warnings,
    )


def recipe() -> WorkflowRecipe:
    return WorkflowRecipe(
        code="nuovo_incarico",
        title="Nuovo incarico",
        description="Riduce apertura pratica, conflitti, preventivo e checklist senza creare dati critici automaticamente.",
        risk_level="medium",
        baseline_minutes=90,
        builder=build,
    )

