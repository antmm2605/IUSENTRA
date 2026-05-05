from __future__ import annotations

import pytest

from pct.editor_ai.edit_proposals import apply_edit_proposal_to_html, build_edit_proposals
from pct.editor_ai.validators import EditorAIValidationError


def test_followup_crea_proposta_pending_non_applicata():
    proposals = build_edit_proposals(
        atto_ai_id="atto-1",
        version_id="ver-1",
        instructions='Sostituisci "vecchio" con "nuovo"',
        current_html="<p>Testo vecchio.</p>",
        created_by="utente",
    )

    assert proposals[0].status == "pending"
    assert proposals[0].operation_type == "replace"
    assert proposals[0].find_text == "vecchio"


def test_accettazione_applica_modifica_puntuale():
    proposal = build_edit_proposals(
        atto_ai_id="atto-1",
        version_id="ver-1",
        instructions='Sostituisci "vecchio" con "nuovo"',
        current_html="<p>Testo vecchio.</p>",
        created_by="utente",
    )[0]

    updated, warnings = apply_edit_proposal_to_html("<p>Testo vecchio.</p>", proposal)

    assert "nuovo" in updated
    assert warnings == []


def test_modifica_con_numerazione_produce_warning():
    proposal = build_edit_proposals(
        atto_ai_id="atto-1",
        version_id="ver-1",
        instructions="Aggiungi una sezione sulle prove documentali",
        current_html="<ol><li>Primo motivo</li></ol>",
        created_by="utente",
    )[0]

    updated, warnings = apply_edit_proposal_to_html("<ol><li>Primo motivo</li></ol>", proposal)

    assert "Integrazione richiesta" in updated
    assert any("numerazione" in warning.lower() for warning in warnings)


def test_istruzioni_vuote_falliscono():
    with pytest.raises(EditorAIValidationError):
        build_edit_proposals(
            atto_ai_id="atto-1",
            version_id="ver-1",
            instructions=" ",
            current_html="<p>Testo</p>",
            created_by="utente",
        )
