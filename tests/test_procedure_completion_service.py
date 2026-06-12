"""Orchestratore: preview, review, approve, publish fail-closed."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from pct.procedure_completion.repository import ProcedureCompletionRepository
from pct.procedure_completion.service import (
    ProcedureCompletionError,
    ProcedureCompletionService,
)

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "procedure_completion" / "512075_accordo_ristrutturazione_input.json").read_text(
        encoding="utf-8"
    )
)

CTX = {
    "tenant_id": "studio1",
    "user_id": "avv.verdi",
    "permissions": {
        "procedure_completion.leggi",
        "procedure_completion.esegui",
        "procedure_completion.approva",
        "procedure_completion.pubblica",
    },
}


@pytest.fixture()
def service(tmp_path):
    return ProcedureCompletionService(ProcedureCompletionRepository(tmp_path / "pce.db"))


def test_preview_da_codice_reale_salva_card_e_validation(service):
    esito = service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione ante causam"}, CTX)
    assert esito["ok"] is True
    card = esito["card"]
    assert card["codice"] == "010003"
    assert card["sources"], "fonti collegate"
    assert card["citations"], "citazioni estratte dalle fonti"
    assert esito["validation"]["approvable"] is True
    riletta = service.get_card(card["id"], CTX)
    assert riletta.codice == "010003"


def test_workflow_review_approve_publish(service):
    card_id = service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, CTX)["card"]["id"]
    service.submit_for_review(card_id, CTX)
    approvata = service.approve_completion(card_id, reviewer="Avv. Verdi", reason="verificata", context=CTX)
    assert approvata["card"]["status"] == "approved"
    pubblicata = service.publish_completion(card_id, CTX)
    assert pubblicata["card"]["status"] == "published"
    assert pubblicata["validation"]["publishable"] is True


def test_publish_richiede_stato_approved(service):
    card_id = service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, CTX)["card"]["id"]
    with pytest.raises(ProcedureCompletionError):
        service.publish_completion(card_id, CTX)


def test_512075_needs_review_e_non_approvabile(service):
    esito = service.preview_completion(FIXTURE["input"], CTX)
    card = esito["card"]
    assert card["status"] == "needs_review"
    assert any(gap["codice_gap"] == "codice_non_in_catalogo" for gap in card["gap_evidenza"])
    with pytest.raises(ProcedureCompletionError):
        service.approve_completion(card["id"], reviewer="Avv. Verdi", context=CTX)


def test_explain_article_solo_da_citazioni_collegate(service):
    card_id = service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, CTX)["card"]["id"]
    spiegazione = service.explain_article(card_id, "art. 633 c.p.c.", CTX)
    assert spiegazione["ok"] is True
    assert spiegazione["citations"]
    assert "consulenza" in spiegazione["disclaimer"].lower()
    sconosciuto = service.explain_article(card_id, "art. 9999 c.p.c.", CTX)
    assert sconosciuto["ok"] is False
    assert sconosciuto["needs_review"] is True
    assert sconosciuto["next_actions"], "azioni successive proposte invece di inventare"


def test_suggest_template_espone_candidati_e_gap(service, tmp_path):
    def template_search(question, **kwargs):
        return {"best_template": {"id": "TPL1", "titolo": "Ricorso monitorio", "match_score": 90}, "alternatives": []}

    con_template = ProcedureCompletionService(
        ProcedureCompletionRepository(tmp_path / "pce2.db"), template_search=template_search
    )
    card_id = con_template.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, CTX)["card"]["id"]
    suggerimento = con_template.suggest_template(card_id, CTX)
    assert suggerimento["templateSelected"]["template_id"] == "TPL1"
    assert suggerimento["needs_review"] is False

    senza = service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, CTX)["card"]
    esito = service.suggest_template(senza["id"], CTX)
    assert esito["needs_review"] is True
    assert esito["gaps"]


def test_permessi_contesto_fail_closed(service):
    solo_lettura = {"tenant_id": "studio1", "user_id": "op", "permissions": {"procedure_completion.leggi"}}
    with pytest.raises(ProcedureCompletionError):
        service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, solo_lettura)
    card_id = service.preview_completion({"codice": "010003", "denominazione": "Procedimento di ingiunzione"}, CTX)["card"]["id"]
    with pytest.raises(ProcedureCompletionError):
        service.approve_completion(card_id, reviewer="x", context=solo_lettura)


def test_input_invalido_rifiutato(service):
    with pytest.raises(ProcedureCompletionError):
        service.preview_completion({"codice": "", "denominazione": ""}, CTX)
    with pytest.raises(ProcedureCompletionError):
        service.preview_completion({"codice": "ABC-XYZ!", "denominazione": "Test procedura valida"}, CTX)
