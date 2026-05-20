from __future__ import annotations

import pytest

from pct.evidence_vault import add_evidence_document
from pct.post_acceptance_obligations import complete_obligation, evaluate_post_acceptance_obligations
from tests.procedure_pipeline_support import make_repo


def test_obblighi_post_accettazione_per_prefissi_e_review(tmp_path):
    repo = make_repo(tmp_path)

    ids_010 = evaluate_post_acceptance_obligations(
        repo,
        fascicolo_id="F010",
        procedure_code="PROC",
        xsd_code="010001",
        trigger_event="DECRETO_EMESSO",
    )
    obligations_010 = repo.list_obligations("F010")
    assert {"NOTIFICA", "RELATA", "DEPOSITO_PROVA_NOTIFICA", "ALTRO"} <= {row["obligation_type"] for row in obligations_010}
    assert all(int(row["human_review_required"]) == 1 for row in obligations_010)

    ids_030 = evaluate_post_acceptance_obligations(
        repo,
        fascicolo_id="F030",
        procedure_code="PROC",
        xsd_code="030001",
        trigger_event="APERTURA",
    )
    assert {"NOTIFICA", "RELATA"} == {row["obligation_type"] for row in repo.list_obligations("F030")}

    evaluate_post_acceptance_obligations(
        repo,
        fascicolo_id="F999",
        procedure_code="PROC",
        xsd_code="999001",
        trigger_event="ACCETTAZIONE",
    )
    assert {"MONITORAGGIO_PROVVEDIMENTO", "ALTRO"} == {row["obligation_type"] for row in repo.list_obligations("F999")}

    proof_obligation = next(row for row in obligations_010 if row["evidence_required_json"] == ["PROOF_OF_DELIVERY"])
    with pytest.raises(ValueError):
        complete_obligation(repo, int(proof_obligation["id"]))
    add_evidence_document(repo, fascicolo_id="F010", evidence_type="PROOF_OF_DELIVERY", document_id="proof1", hash="h")
    complete_obligation(repo, int(proof_obligation["id"]))
    completed = next(row for row in repo.list_obligations("F010") if int(row["id"]) == int(proof_obligation["id"]))
    assert completed["obligation_status"] == "COMPLETED"
    assert ids_030
