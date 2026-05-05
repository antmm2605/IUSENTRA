from __future__ import annotations

import pytest

from pct.editor_ai.models import AttoDraftPlan, AttoDraftSection
from pct.editor_ai.validators import EditorAIValidationError, detect_english_headings, validate_italian_text, validate_plan


def test_validator_rifiuta_intestazioni_inglesi():
    with pytest.raises(EditorAIValidationError):
        validate_italian_text("Case Summary\nKey Points", field_name="bozza")


def test_validator_accetta_testo_italiano():
    warnings = validate_italian_text("Sintesi del fascicolo e punti rilevanti della controversia.", field_name="bozza")

    assert warnings == []
    assert detect_english_headings("Sintesi del fascicolo") == []


def test_plan_con_titoli_italiani_e_sezioni_obbligatorie():
    plan = AttoDraftPlan(
        title="Comparsa di costituzione",
        tipo_atto="Comparsa",
        template_id="comparsa",
        sections=[
            AttoDraftSection(
                id="premesse",
                heading="Premesse in fatto",
                level=1,
                purpose="Ricostruzione dei fatti",
            )
        ],
    )

    warnings = validate_plan(plan)

    assert all("ingles" not in warning.lower() for warning in warnings)
