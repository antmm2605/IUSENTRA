"""Proposte di modifica puntuali per atti Editor AI."""

from __future__ import annotations

import re

from .models import AttoAIEditProposal, new_id, utc_now
from .validators import EditorAIValidationError, clean_text, validate_edit_operation


def build_edit_proposals(
    *,
    atto_ai_id: str,
    version_id: str,
    instructions: str,
    current_html: str,
    created_by: str,
) -> list[AttoAIEditProposal]:
    clean_instructions = clean_text(instructions)
    if not clean_instructions:
        raise EditorAIValidationError("Istruzioni modifica mancanti.")

    proposals: list[AttoAIEditProposal] = []
    now = utc_now()
    lower = clean_instructions.lower()

    replace_match = re.search(r"sostituisc[ia]\s+['\"](.+?)['\"]\s+con\s+['\"](.+?)['\"]", clean_instructions, re.IGNORECASE)
    if replace_match:
        operation = "replace"
        proposals.append(
            AttoAIEditProposal(
                id=new_id("editatto"),
                atto_ai_id=atto_ai_id,
                version_id=version_id,
                status="pending",
                operation_type=operation,
                target_block_id=None,
                find_text=replace_match.group(1),
                replace_text=replace_match.group(2),
                insert_text=None,
                reason="Sostituzione puntuale richiesta dall'utente.",
                created_by=created_by,
                created_at=now,
            )
        )
    elif any(token in lower for token in ("aggiungi", "inserisci", "integra")):
        operation = "add_section"
        title = "Integrazione richiesta"
        proposals.append(
            AttoAIEditProposal(
                id=new_id("editatto"),
                atto_ai_id=atto_ai_id,
                version_id=version_id,
                status="pending",
                operation_type=operation,
                target_block_id=None,
                find_text=None,
                replace_text=None,
                insert_text=f"<h2>{title}</h2><p>{clean_instructions}</p>",
                reason="Integrazione proposta come nuova sezione per revisione umana.",
                created_by=created_by,
                created_at=now,
            )
        )
    else:
        operation = "rewrite_section"
        proposals.append(
            AttoAIEditProposal(
                id=new_id("editatto"),
                atto_ai_id=atto_ai_id,
                version_id=version_id,
                status="pending",
                operation_type=operation,
                target_block_id=None,
                find_text=None,
                replace_text=None,
                insert_text=f"<p>{clean_instructions}</p>",
                reason="Modifica proposta come riscrittura locale da approvare nell'editor.",
                created_by=created_by,
                created_at=now,
            )
        )

    for proposal in proposals:
        validate_edit_operation(proposal.operation_type)
    return proposals


def apply_edit_proposal_to_html(current_html: str, proposal: AttoAIEditProposal) -> tuple[str, list[str]]:
    warnings: list[str] = []
    operation = validate_edit_operation(proposal.operation_type)
    html = str(current_html or "")
    if operation == "replace":
        find_text = proposal.find_text or ""
        replace_text = proposal.replace_text or ""
        if not find_text:
            raise EditorAIValidationError("Testo da sostituire mancante.")
        if find_text not in html:
            raise EditorAIValidationError("Il testo da sostituire non e' presente nel documento corrente.")
        return html.replace(find_text, replace_text, 1), warnings
    if operation == "delete":
        find_text = proposal.find_text or ""
        if not find_text or find_text not in html:
            raise EditorAIValidationError("Testo da eliminare non presente.")
        return html.replace(find_text, "", 1), warnings
    if operation in {"insert_after", "insert_before"}:
        find_text = proposal.find_text or ""
        insert = proposal.insert_text or ""
        if not find_text or find_text not in html:
            raise EditorAIValidationError("Punto di inserimento non presente.")
        replacement = f"{find_text}{insert}" if operation == "insert_after" else f"{insert}{find_text}"
        return html.replace(find_text, replacement, 1), warnings
    if operation in {"rewrite_section", "add_section"}:
        insert = proposal.insert_text or proposal.replace_text or ""
        if not insert:
            raise EditorAIValidationError("Contenuto proposta mancante.")
        if "<ol" in html or "<ul" in html:
            warnings.append("Verificare numerazione e rinvii dopo l'accettazione della modifica.")
        return f"{html}\n{insert}", warnings
    raise EditorAIValidationError("Operazione modifica non supportata.")
