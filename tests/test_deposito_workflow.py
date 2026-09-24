from __future__ import annotations

import pytest

from web.services.deposito_pec_runtime import (
    deposito_workflow_state,
    mark_deposito_workflow_stage,
    preserve_deposito_workflow,
    validate_deposito_action_preparation,
)


def _preparation(*, body: str = "Corpo PEC") -> dict:
    return {
        "tipo_deposito_telematico_key": "SICID::Ricorso",
        "tipo_deposito_telematico_policy": "PCT",
        "datiatto_extra": {"professionista_ruolo": "AVVOCATO"},
        "corpo_pec": body,
        "documents": [
            {
                "documentId": "ATTO1",
                "selected": True,
                "role": "atto_principale",
                "studioDocumentType": "AttoPrincipale",
                "alreadySigned": True,
                "requiresSignature": False,
                "additionalSignature": False,
            },
            {
                "documentId": "RT1",
                "selected": True,
                "role": "allegato",
                "studioDocumentType": "RicevutaPagamento",
                "alreadySigned": False,
                "requiresSignature": False,
                "additionalSignature": False,
            },
        ],
    }


def test_workflow_persiste_solo_esiti_positivi_in_sequenza():
    preparation = preserve_deposito_workflow(_preparation(), None)
    profile = {"preparazione_busta": preparation}

    with pytest.raises(ValueError, match="prova senza invio"):
        mark_deposito_workflow_stage(profile, "simulation")

    profile = mark_deposito_workflow_stage(profile, "proof", id_deposito="BUSTA1")
    state = deposito_workflow_state(profile["preparazione_busta"])
    assert state["proof"]["ok"] is True
    assert state["simulation"]["ok"] is False
    assert state["send"]["ok"] is False

    profile = mark_deposito_workflow_stage(profile, "simulation", id_deposito="BUSTA1")
    profile = mark_deposito_workflow_stage(profile, "send", id_deposito="BUSTA1")
    state = deposito_workflow_state(profile["preparazione_busta"])
    assert state["proof"]["ok"] is True
    assert state["simulation"]["ok"] is True
    assert state["send"]["ok"] is True

    with pytest.raises(ValueError, match="secondo invio"):
        mark_deposito_workflow_stage(profile, "send", id_deposito="BUSTA1")


def test_workflow_identico_si_conserva_e_modifica_riparte_da_zero():
    first = preserve_deposito_workflow(_preparation(), None)
    profile = {"preparazione_busta": first}
    profile = mark_deposito_workflow_stage(profile, "proof", id_deposito="BUSTA1")
    profile = mark_deposito_workflow_stage(profile, "simulation", id_deposito="BUSTA1")

    same = preserve_deposito_workflow(_preparation(), profile["preparazione_busta"])
    same_state = deposito_workflow_state(same)
    assert same_state["proof"]["ok"] is True
    assert same_state["simulation"]["ok"] is True

    changed = preserve_deposito_workflow(
        _preparation(body="Corpo PEC modificato"),
        profile["preparazione_busta"],
    )
    changed_state = deposito_workflow_state(changed)
    assert changed_state["proof"]["ok"] is False
    assert changed_state["simulation"]["ok"] is False
    assert changed_state["send"]["ok"] is False


def test_workflow_form_deve_coincidere_con_preparazione_salvata():
    preparation = preserve_deposito_workflow(_preparation(), None)
    state = validate_deposito_action_preparation(
        preparation,
        type_key="SICID::Ricorso",
        datiatto_extra={"professionista_ruolo": "AVVOCATO"},
        corpo_pec="Corpo PEC",
        selected_document_ids=["RT1", "ATTO1"],
        main_document_id="ATTO1",
    )
    assert state["proof"]["ok"] is False

    with pytest.raises(ValueError, match="documenti del deposito sono cambiati"):
        validate_deposito_action_preparation(
            preparation,
            type_key="SICID::Ricorso",
            datiatto_extra={"professionista_ruolo": "AVVOCATO"},
            corpo_pec="Corpo PEC",
            selected_document_ids=["ATTO1"],
            main_document_id="ATTO1",
        )


def test_reset_esplicito_avvia_un_ciclo_nuovo_anche_con_stessa_busta():
    first = preserve_deposito_workflow(_preparation(), None)
    profile = {"preparazione_busta": first}
    profile = mark_deposito_workflow_stage(profile, "proof", id_deposito="BUSTA1")
    profile = mark_deposito_workflow_stage(profile, "simulation", id_deposito="BUSTA1")
    profile = mark_deposito_workflow_stage(profile, "send", id_deposito="BUSTA1")

    reset = preserve_deposito_workflow(
        profile["preparazione_busta"],
        profile["preparazione_busta"],
        reset=True,
    )
    state = deposito_workflow_state(reset)
    assert state["proof"]["ok"] is False
    assert state["simulation"]["ok"] is False
    assert state["send"]["ok"] is False
